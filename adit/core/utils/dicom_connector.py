# pyright: basic
"""
The connector directly communicates with the DICOM servers by using pynetdicom.

Error handling and logging is quite complex here. All lower level methods
(_find, _get, _move, _store) only raise a ConnectionError if the connection
itself fails, but not if some operation itself (inside a working connection)
fails. Those failures are recognized and raised in all higher level methods
(find_patients, download_study, ...). A higher level method that uses another
higher level method does catch the exception and raises one itself. Loggings
only occur in higher level methods that uses lower level methods. As logger
the Celery task logger is used as we intercept those messages and save them
in TransferTask model object.
"""
import asyncio
import datetime
import errno
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import wraps
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    cast,
)

from django.conf import settings
from pydicom import dcmread, uid, valuerep
from pydicom.datadict import dictionary_VM
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError
from pynetdicom import debug_logger, evt
from pynetdicom._globals import STATUS_PENDING, STATUS_SUCCESS
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.events import Event
from pynetdicom.presentation import (
    BasicWorklistManagementPresentationContexts,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
    build_role,
)
from pynetdicom.sop_class import (
    EncapsulatedMTLStorage,  # pyright: ignore
    EncapsulatedOBJStorage,  # pyright: ignore
    EncapsulatedSTLStorage,  # pyright: ignore
    PatientRootQueryRetrieveInformationModelFind,  # pyright: ignore
    PatientRootQueryRetrieveInformationModelGet,  # pyright: ignore
    PatientRootQueryRetrieveInformationModelMove,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelFind,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelGet,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelMove,  # pyright: ignore
)
from pynetdicom.status import code_to_category

from ..errors import RetriableTaskError
from ..models import DicomServer
from .file_transmit import FileTransmitClient, Metadata
from .sanitize import sanitize_dirname

logger = logging.getLogger(__name__)

DimseService = Literal["C_FIND", "C_GET", "C_MOVE", "C_STORE"]
Modifier = Callable[[Dataset], None]


def connect_to_server(service: DimseService):
    """Automatically handles the connection when `auto_config` option is set.

    Opens and closes the connecition to the DICOM server when a method is
    decorated with this function. Only a connection is opened for the most
    outer function that is called. So if the method itself calls a method
    that is also decorated with this function then the connection is reused
    and the connection is closed by the most outer method automatically.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            opened_connection = False

            is_connected = self.assoc and self.assoc.is_alive()
            if self.config.auto_connect and not is_connected:
                self.open_connection(service)
                opened_connection = True

            result = func(self, *args, **kwargs)

            if opened_connection and self.config.auto_connect:
                self.close_connection()
                opened_connection = False

            return result

        return wrapper

    return decorator


class DicomConnector:
    @dataclass
    class Config:
        auto_connect: bool = True
        connection_retries: int = 2
        retry_timeout: int = 30  # in seconds
        acse_timeout: Optional[int] = None
        dimse_timeout: Optional[int] = None
        network_timeout: Optional[int] = None

    def __init__(
        self,
        server: DicomServer,
        config: Config | None = None,
    ):
        self.server = server
        if config is None:
            self.config = DicomConnector.Config()
        else:
            self.config = config

        if settings.ENABLE_DICOM_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

        self.assoc = None

    def open_connection(self, service: DimseService):
        if self.assoc:
            raise AssertionError("A former connection was not closed properly.")

        logger.debug("Opening connection to DICOM server %s.", self.server.ae_title)

        for i in range(self.config.connection_retries + 1):
            try:
                self._associate(service)
                break
            except ConnectionError as err:
                logger.exception("Could not connect to %s.", self.server)
                if i < self.config.connection_retries:
                    logger.info(
                        "Retrying to connect in %d seconds.",
                        self.config.retry_timeout,
                    )
                    time.sleep(self.config.retry_timeout)
                else:
                    raise err

    def close_connection(self):
        if not self.assoc:
            raise AssertionError("No association to release.")

        logger.debug("Closing connection to DICOM server %s.", self.server.ae_title)

        self.assoc.release()
        self.assoc = None

    def abort_connection(self):
        if not self.assoc:
            raise AssertionError("No association to abort.")

        logger.debug("Aborting connection to DICOM server %s.", self.server.ae_title)

        self.assoc.abort()

    def find_patients(
        self, query: dict[str, Any], limit_results: int | None = None
    ) -> list[dict[str, Any]]:
        if self.server.patient_root_find_support:
            query["QueryRetrieveLevel"] = "PATIENT"
        else:
            query["QueryRetrieveLevel"] = "STUDY"

        patients = self._send_c_find(
            query,
            limit_results=limit_results,
        )

        # Make patients unique, since querying on study level will
        # return all studies for one patient, resulting in duplicate patients
        if query["QueryRetrieveLevel"] == "STUDY":
            seen = set()
            unique_patients = [
                patient
                for patient in patients
                if patient["PatientID"] not in seen and not seen.add(patient["PatientID"])
            ]
            patients = unique_patients

        # Some PACS servers (like our Synapse) don't support a query filter of PatientBirthDate
        # as it is optional in the Patient Root Query/Retrieve Information Model,
        # see https://groups.google.com/g/comp.protocols.dicom/c/h28r_znomEw
        # In those cases we we have to filter programmatically.
        # TODO allow range filter (but not needed at the moment)
        birth_date = query.get("PatientBirthDate")
        if birth_date:
            return [patient for patient in patients if patient["PatientBirthDate"] == birth_date]

        return patients

    def find_studies(self, query: dict[str, Any], limit_results: Optional[int] = None):
        query["QueryRetrieveLevel"] = "STUDY"

        if "NumberOfStudyRelatedInstances" not in query:
            query["NumberOfStudyRelatedInstances"] = ""

        # We filter for StudyDescription programmatically, so that we can use
        # more advanced regular expressions.
        study_description = query.get("StudyDescription")
        if study_description:
            study_description = study_description.lower()
            query["StudyDescription"] = ""

        studies = self._send_c_find(query, limit_results=limit_results)

        if study_description:
            studies = list(
                filter(
                    lambda x: re.search(study_description, x["StudyDescription"].lower()),
                    studies,
                )
            )

        query_modalities = query.get("ModalitiesInStudy")
        if not query_modalities:
            return studies

        return self._filter_studies_by_modalities(studies, query_modalities)

    def find_series(self, query: dict[str, Any], limit_results=None):
        """Fetch all series UIDs for a given study UID.

        The series can be filtered by a modality (or a list of modalities for
        multiple modalities). If no modality is set all series of the study
        will be returned.
        """
        query["QueryRetrieveLevel"] = "SERIES"

        # We filter for Modality and SeriesNumber programmatically because we allow
        # to filter for multiple modalities resp. series numbers. So we have to
        # cache them in a variable and set them to a blank string for the C-Find query.
        modalities = query.get("Modality")
        if modalities:
            if not isinstance(modalities, list):
                modalities = [modalities]

            query["Modality"] = ""

        # It's also better to filter Series Number programmatically, because it's of
        # VR Integer String and with just a C-Find it's not guaranteed that e.g.
        # "4" is the same as "+4"
        # https://groups.google.com/g/comp.protocols.dicom/c/JNsg7upVJ08
        series_numbers = query.get("SeriesNumber")
        if series_numbers:
            # Convert to an integer for better comparison.
            if not isinstance(series_numbers, list):
                series_numbers = [int(series_numbers)]
            else:
                series_numbers = map(int, series_numbers)

            query["SeriesNumber"] = ""

        # We also filter for SeriesDescription programmatically, so that way we can use
        # more advanced regular expressions.
        series_description = query.get("SeriesDescription")
        if series_description:
            series_description = series_description.lower()
            query["SeriesDescription"] = ""

        series_list = self._send_c_find(query, limit_results=limit_results)

        if modalities:
            series_list = list(
                filter(
                    lambda x: x["Modality"] in modalities,
                    series_list,
                )
            )

        if series_numbers:
            series_list = list(
                filter(
                    lambda x: int(x["SeriesNumber"]) in series_numbers,
                    series_list,
                )
            )

        if series_description:
            series_list = list(
                filter(
                    lambda x: re.search(series_description, x["SeriesDescription"].lower()),
                    series_list,
                )
            )

        return series_list

    def download_study(
        self,
        patient_id: str,
        study_uid: str,
        dest_folder: PathLike,
        modality: Optional[str] = None,
        modifier: Modifier | None = None,
    ):
        series_list = self.find_series(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "Modality": modality,
                "SeriesInstanceUID": "",
                "SeriesDescription": "",
                "SeriesNumber": "",
            }
        )

        for series in series_list:
            series_uid = series["SeriesInstanceUID"]
            modality = series["Modality"]

            if modality in settings.EXCLUDED_MODALITIES:
                continue

            # TODO maybe we should move the series folder name creation to the
            # store handler as it is not guaranteed that all PACS servers
            # do return the SeriesDescription with C-FIND
            series_folder_name = sanitize_dirname(series["SeriesDescription"])
            download_path = Path(dest_folder) / series_folder_name

            self.download_series(patient_id, study_uid, series_uid, download_path, modifier)

        logger.debug("Successfully downloaded study %s.", study_uid)

    def download_series(
        self,
        patient_id: str,
        study_uid: str,
        series_uid: str,
        dest_folder: PathLike,
        modifier: Modifier | None = None,
    ):
        """Download all series to a specified folder for given series UIDs and pseudonymize
        the dataset before storing it to disk."""

        query = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }

        if self.server.patient_root_get_support or self.server.study_root_get_support:
            self._download_series_with_c_get(query, dest_folder, modifier)
            logger.debug("Successfully downloaded series %s of study %s.", series_uid, study_uid)
        elif self.server.patient_root_move_support or self.server.study_root_move_support:
            self._download_series_with_c_move(query, dest_folder, modifier)
            logger.debug("Successfully downloaded series %s of study %s.", series_uid, study_uid)
        else:
            raise ValueError("No Query/Retrieve Information Model supported to download images.")

    def upload_folder(self, source_folder: PathLike):
        """Upload a specified folder to a DICOM server."""

        if not self.server.store_scp_support:
            raise ValueError("Destination server doesn't support C-STORE operations.")

        results = self._send_c_store(source_folder)

        has_success = False
        has_failure = False
        for result in results:
            status_category = result["status"]["category"]
            status_code = result["status"]["code"]
            image_uid = result["data"]["SOPInstanceUID"]
            if status_category == STATUS_SUCCESS:
                has_success = True
            if status_category != STATUS_SUCCESS:
                has_failure = True
                logger.error(
                    "Failed to upload image %s with status %s (%s).",
                    image_uid,
                    status_category,
                    status_code,
                )

        if results and has_failure:
            if not has_success:
                raise RetriableTaskError("Failed to upload all images.")
            raise RetriableTaskError("Failed to upload some images.")

    def move_study(
        self,
        patient_id: str,
        study_uid: str,
        dest_aet: str,
        modality: Optional[str] = None,
    ):
        series_list = self.find_series(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "Modality": modality,
                "SeriesInstanceUID": "",
                "SeriesDescription": "",
                "SeriesNumber": "",
            }
        )

        has_success = False
        has_failure = False
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]
            modality = series["Modality"]

            if modality in settings.EXCLUDED_MODALITIES:
                continue

            try:
                self.move_series(patient_id, study_uid, series, dest_aet)
                has_success = True
            except ValueError:
                logger.exception("Failed to move series %s.", series_uid)
                has_failure = True

        if series_list and has_failure:
            if not has_success:
                raise RetriableTaskError("Failed to move all series.")
            raise RetriableTaskError("Failed to move some series.")

    def move_series(self, patient_id: str, study_uid: str, series_uid: str, dest_aet: str):
        query = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }

        results = self._send_c_move(
            query,
            dest_aet,
        )

        _evaluate_get_move_results(results, query)

    def fetch_study_modalities(self, patient_id: str, study_uid: str):
        """Fetch all modalities of a study and return them in a list."""

        try:
            series_list = self.find_series(
                {"PatientID": patient_id, "StudyInstanceUID": study_uid, "Modality": ""}
            )
        except ValueError as err:
            logger.exception("Failed to fetch modalities of study %s.", study_uid)
            raise RetriableTaskError("Failed to fetch modalities of study.") from err

        modalities = set(map(lambda x: x["Modality"], series_list))
        return sorted(list(modalities))

    def _associate(self, service: DimseService):
        ae = AE(settings.ADIT_AE_TITLE)

        # Speed up by reducing the number of required DIMSE messages
        # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
        ae.maximum_pdu_size = 0

        # We only use the timeouts if set, otherwise we leave the default timeouts
        if self.config.acse_timeout is not None:
            ae.acse_timeout = self.config.acse_timeout
        if self.config.dimse_timeout is not None:
            ae.dimse_timeout = self.config.dimse_timeout
        if self.config.network_timeout is not None:
            ae.network_timeout = self.config.network_timeout

        # Setup the contexts
        # (inspired by https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/apps)
        ext_neg = []
        if service == "C_FIND":
            ae.requested_contexts = (
                QueryRetrievePresentationContexts + BasicWorklistManagementPresentationContexts
            )
        elif service == "C_GET":
            # We must exclude as many storage contexts as query/retrieve contexts we add
            # because the maximum requested contexts is 128. "StoragePresentationContexts" is a list
            # that contains 128 storage contexts itself.
            exclude = [
                EncapsulatedSTLStorage,
                EncapsulatedOBJStorage,
                EncapsulatedMTLStorage,
            ]
            store_contexts = [
                cx for cx in StoragePresentationContexts if cx.abstract_syntax not in exclude
            ]
            ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
            ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
            for cx in store_contexts:
                assert cx.abstract_syntax is not None
                ae.add_requested_context(cx.abstract_syntax)
                ext_neg.append(build_role(cx.abstract_syntax, scp_role=True))
        elif service == "C_MOVE":
            ae.requested_contexts = QueryRetrievePresentationContexts
        elif service == "C_STORE":
            ae.requested_contexts = StoragePresentationContexts
        else:
            raise ValueError(f"Invalid DIMSE service: {service}")

        self.assoc = ae.associate(
            self.server.host,
            self.server.port,
            ae_title=self.server.ae_title,
            ext_neg=ext_neg,
        )

        if not self.assoc.is_established:
            logger.error("Could not connect to %s.", self.server)
            raise RetriableTaskError(f"Could not connect to {self.server}.")

    @connect_to_server("C_FIND")
    def _send_c_find(
        self,
        query_dict: dict[str, Any],
        limit_results: Optional[int] = None,
        msg_id: int = 1,
    ):
        logger.debug("Sending C-FIND with query: %s", query_dict)

        level = query_dict.get("QueryRetrieveLevel")
        patient_id = _check_required_id(cast(str, query_dict.get("PatientID")))

        if self.server.study_root_find_support and level != "PATIENT":
            query_model = StudyRootQueryRetrieveInformationModelFind
        elif self.server.patient_root_find_support and (level == "PATIENT" or patient_id):
            query_model = PatientRootQueryRetrieveInformationModelFind
        else:
            raise ValueError("No valid Query/Retrieve Information Model for C-FIND could be found.")

        query_ds = _make_query_dataset(query_dict)
        assert self.assoc is not None
        responses = self.assoc.send_c_find(query_ds, query_model, msg_id)
        results = self._fetch_results(responses, "C-FIND", query_dict, limit_results)
        return _extract_pending_data(results)

    @connect_to_server("C_GET")
    def _send_c_get(
        self,
        query_dict: dict[str, Any],
        store_handler: Callable[[Event, list[Exception]], int],
        msg_id: int = 1,
    ):
        logger.debug("Sending C-GET with query: %s", query_dict)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = _check_required_id(cast(str, query_dict.get("PatientID")))
        study_uid = _check_required_id(cast(str, query_dict.get("StudyInstanceUID")))

        if self.server.study_root_get_support and study_uid:
            query_model = StudyRootQueryRetrieveInformationModelGet
        elif self.server.patient_root_get_support and patient_id and study_uid:
            query_model = PatientRootQueryRetrieveInformationModelGet
        else:
            raise ValueError(
                "No valid Query/Retrieve Information Model for C-GET could be selected."
            )

        # A list to store errors that might be raised by the store handler
        store_errors: list[Exception] = []

        query_ds = _make_query_dataset(query_dict)
        assert self.assoc is not None

        self.assoc.bind(evt.EVT_C_STORE, store_handler, [store_errors])

        try:
            assert self.assoc is not None
            responses = self.assoc.send_c_get(query_ds, query_model, msg_id)
            results = self._fetch_results(responses, "C-GET", query_dict)
        except Exception as err:
            # The exception might happen cause of an abort by the store handler, so we
            # check if an error was added in the store handler.
            if store_errors:
                raise store_errors[0]

            # Otherwise just raise the original error
            raise err
        finally:
            self.assoc.unbind(evt.EVT_C_STORE, store_handler)

        return results

    @connect_to_server("C_MOVE")
    def _send_c_move(self, query_dict: dict[str, Any], dest_aet: str, msg_id: int = 1):
        logger.debug("Sending C-MOVE with query: %s", query_dict)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = _check_required_id(cast(str, query_dict.get("PatientID")))
        study_uid = _check_required_id(cast(str, query_dict.get("StudyInstanceUID")))

        if self.server.study_root_move_support and study_uid:
            query_model = StudyRootQueryRetrieveInformationModelMove
        elif self.server.patient_root_move_support and patient_id and study_uid:
            query_model = PatientRootQueryRetrieveInformationModelMove
        else:
            raise ValueError(
                "No valid Query/Retrieve Information Model for C-MOVE could be selected."
            )

        query_ds = _make_query_dataset(query_dict)
        assert self.assoc is not None
        responses = self.assoc.send_c_move(query_ds, dest_aet, query_model, msg_id)
        return self._fetch_results(responses, "C-MOVE", query_dict)

    @connect_to_server("C_STORE")
    def _send_c_store(
        self,
        source_folder: PathLike,
        modifier: Modifier | None = None,
        msg_id: int = 1,
    ):
        logger.debug("Sending C-STORE of folder: %s", source_folder)

        if not self.server.store_scp_support:
            raise ValueError("C-STORE operation not supported by server.")

        results = []
        for path in Path(source_folder).rglob("*"):
            if not path.is_file():
                continue

            try:
                ds = dcmread(path)
            except InvalidDicomError:
                logger.warning("Tried to read invalid DICOM file %s. Skipping it.", path)
                continue

            # Allow to manipulate the dataset by a modifier function
            if modifier:
                modifier(ds)

            assert self.assoc is not None
            status = self.assoc.send_c_store(ds, msg_id)

            if status:
                results.append(
                    {
                        "status": {
                            "code": status.Status,
                            "category": code_to_category(status.Status),
                        },
                        "data": {"SOPInstanceUID": ds.SOPInstanceUID},
                    }
                )
            else:
                logger.error(
                    "Connection timed out, was aborted or received invalid "
                    "response during C-STORE of folder: %s",
                    source_folder,
                )
                raise RetriableTaskError(
                    "Connection timed out, was aborted or received invalid during C-STORE."
                )

        return results

    def _fetch_results(
        self,
        responses: Iterator[Tuple[Dataset, Dataset | None]],
        operation: str,
        query_dict: dict[str, Any],
        limit_results: Optional[int] = None,
    ):
        results = []
        for status, identifier in responses:
            if limit_results is not None and len(results) >= limit_results:
                self.abort_connection()
                break

            if status:
                data = {}
                if identifier:
                    data.update(_dictify_dataset(identifier))

                results.append(
                    {
                        "status": {
                            "code": status.Status,
                            "category": code_to_category(status.Status),
                        },
                        "data": data,
                    }
                )
            else:
                logger.error(
                    "Connection timed out, was aborted or received invalid "
                    "response during %s with query: {%s}",
                    operation,
                    query_dict,
                )
                raise RetriableTaskError(
                    "Connection timed out, was aborted or received invalid " f"during {operation}."
                )
        return results

    def _filter_studies_by_modalities(
        self, studies: List[Dict[str, Any]], query_modalities: Union[str, List[str]]
    ) -> List[Dict[str, Any]]:
        filtered_studies = []
        for study in studies:
            study_modalities = study.get("ModalitiesInStudy")
            number_images = int(study.get("NumberOfStudyRelatedInstances") or 1)

            if study_modalities and isinstance(study_modalities, list):
                filtered_studies.append(study)

            elif study_modalities and isinstance(study_modalities, str):
                # ModalitiesInStudy returns multiple modalities in a list, but only one
                # modality as a string (at least with the Synapse PACS). So we convert the
                # later one to a list.
                study["ModalitiesInStudy"] = [study_modalities]
                filtered_studies.append(study)

            elif not study_modalities and number_images == 0:
                filtered_studies.append(study)

            elif not study_modalities and number_images > 0:
                # Modalities In Study is not supported by all PACS servers. If it is
                # supported then it should be not empty. Otherwise we fetch the modalities
                # of all the series of this study manually.
                study["ModalitiesInStudy"] = self.fetch_study_modalities(
                    study["PatientID"], study["StudyInstanceUID"]
                )

                # When modalities were fetched manually then the studies must also be
                # filtered manually. Cave, when limit_results is used this may lead to less
                # studies then there really exist.
                if (
                    isinstance(query_modalities, str)
                    and query_modalities in study["ModalitiesInStudy"]
                ):
                    filtered_studies.append(study)

                if isinstance(query_modalities, list) and (
                    set(query_modalities) & set(study["ModalitiesInStudy"])
                ):
                    filtered_studies.append(study)

            else:
                raise AssertionError(f"Invalid study modalities: {study_modalities}")

        return filtered_studies

    def _download_series_with_c_get(
        self,
        query: dict[str, Any],
        dest_folder: PathLike,
        modifier: Modifier | None = None,
    ):
        def handle_c_get_store(event: Event, store_errors: list[Exception]):
            ds = event.dataset
            context = event.context

            # Add DICOM File Meta Information
            ds.file_meta = event.file_meta

            # Set the transfer syntax attributes of the dataset
            ds.is_little_endian = context.transfer_syntax.is_little_endian
            ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

            try:
                self._handle_downloaded_image(ds, dest_folder, modifier)
            except Exception as err:
                store_errors.append(err)

                # Unfortunately not all PACS servers support or respect a C-CANCEL request,
                # so we abort the association of the C-STORE and C-GET requests manually.
                # See https://github.com/pydicom/pynetdicom/issues/553
                # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
                event.assoc.abort()
                self.abort_connection()

                return 0xA702  # Out of resources

            return 0x0000  # Success

        results = self._send_c_get(query, handle_c_get_store)
        _evaluate_get_move_results(results, query)

    def _download_series_with_c_move(
        self,
        query: dict[str, Any],
        dest_folder: PathLike,
        modifier: Modifier | None = None,
    ):
        # Fetch all SOPInstanceUIDs in the series so that we can later
        # evaluate if all images were received.
        image_query = dict(query, **{"QueryRetrieveLevel": "IMAGE", "SOPInstanceUID": ""})
        images = self._send_c_find(image_query)
        image_uids = [image["SOPInstanceUID"] for image in images]

        # A list of errors that may occur while receiving the images
        receiving_errors: list[Exception] = []

        # The images are sent to the receiver container (a C-STORE SCP server)
        # by the move operation. Then those are send to a RabbitMQ queue from
        # which we consume them in a separate thread.
        with ThreadPoolExecutor() as executor:
            future = executor.submit(
                self._consume_from_receiver,
                query["StudyInstanceUID"],
                query["SeriesInstanceUID"],
                image_uids,
                dest_folder,
                receiving_errors,
                modifier,
            )

            try:
                results = self._send_c_move(query, settings.ADIT_AE_TITLE)
                _evaluate_get_move_results(results, query)

                # We have to check the result of the future here, otherwise
                # exceptions in the thread would be ignored.
                future.result()
            except Exception as err:
                # We check here if an error occurred in the consumer thread and
                # then do nothing here but handle it in the finally block.
                # The consumer might also have aborted the connection which then raises
                # an exception during C-MOVE.
                if receiving_errors:
                    pass

                # Otherwise just raise the original error
                raise err
            finally:
                if receiving_errors:
                    raise receiving_errors[0]

    def _consume_from_receiver(
        self,
        study_uid: str,
        series_uid: str,
        image_uids: List[str],
        dest_folder: PathLike,
        receiving_errors: list[Exception],
        modifier: Modifier | None = None,
    ):
        async def consume():
            remaining_image_uids = image_uids[:]
            last_image_at = time.time()

            file_transmit = FileTransmitClient(
                settings.FILE_TRANSMIT_HOST,
                settings.FILE_TRANSMIT_PORT,
                dest_folder,
            )

            def eval_images_received():
                if remaining_image_uids:
                    if remaining_image_uids == image_uids:
                        logger.error("No images of series %s received.", series_uid)
                        receiving_errors.append(
                            RetriableTaskError("Failed to download all images with C-MOVE.")
                        )

                    logger.error(
                        "These images of series %s were not received: %s",
                        series_uid,
                        ", ".join(remaining_image_uids),
                    )
                    receiving_errors.append(
                        RetriableTaskError("Failed to download some images with C-MOVE.")
                    )

            async def handle_received_file(data: bytes, metadata: Metadata):
                nonlocal last_image_at
                last_image_at = time.time()

                image_uid = metadata["SOPInstanceUID"]

                if image_uid in remaining_image_uids:
                    ds = dcmread(BytesIO(data))
                    remaining_image_uids.remove(image_uid)

                    try:
                        self._handle_downloaded_image(ds, dest_folder, modifier)
                    except Exception as err:
                        receiving_errors.append(err)

                if image_uid in remaining_image_uids:
                    remaining_image_uids.remove(image_uid)

                if not remaining_image_uids:
                    return True

                return False

            topic = f"{self.server.ae_title}\\{study_uid}\\{series_uid}"
            subscribe_task = asyncio.create_task(
                file_transmit.subscribe(topic, handle_received_file)
            )

            async def check_timeout():
                while True:
                    await asyncio.sleep(1)

                    if subscribe_task.done():
                        break

                    time_since_last_image = time.time() - last_image_at if last_image_at else 0
                    if time_since_last_image > settings.C_MOVE_DOWNLOAD_TIMEOUT:
                        # Don't accept any more images
                        subscribe_task.cancel()

                        logger.error(
                            "C-MOVE download timed out after %d seconds.",
                            round(time_since_last_image),
                        )

                        # We have to call this before aborting the connection because this
                        # can raise an exception with C-MOVE and we need the info then
                        # if all images were received or not.
                        eval_images_received()

                        self.abort_connection()
                        break

            check_timeout_task = asyncio.create_task(check_timeout())

            await asyncio.gather(subscribe_task, check_timeout_task)

            if not receiving_errors:
                eval_images_received()

        asyncio.run(consume())

    def _handle_downloaded_image(
        self,
        ds: Dataset,
        dest_folder: PathLike,
        modifier: Modifier | None,
    ):
        if modifier:
            modifier(ds)

        folder_path = Path(dest_folder)
        file_path = folder_path / ds.SOPInstanceUID

        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            ds.save_as(file_path, write_like_original=False)
        except Exception as err:
            if isinstance(err, OSError) and err.errno == errno.ENOSPC:
                # No space left on destination
                logger.exception("Out of disk space while saving %s.", file_path)
                no_space_error = RetriableTaskError(
                    "Out of disk space on destination.", long_delay=True
                )
                no_space_error.__cause__ = err
                raise no_space_error
            else:
                logger.exception("Failed to save %s.", file_path)
                raise err


def _check_required_id(value: str) -> Union[str, None]:
    if value and "*" not in value and "?" not in value:
        return value
    return None


def _make_query_dataset(query_dict: Dict[str, Any]):
    """Turn a dict into a pydicom dataset for query."""
    ds = Dataset()
    for keyword in query_dict:
        setattr(ds, keyword, query_dict[keyword])
    return ds


def _dictify_dataset(ds: Dataset):
    """Turn a pydicom Dataset into a dict with keys derived from the Element tags.

    Adapted from https://github.com/pydicom/pydicom/issues/319
    """
    output = {}

    for elem in ds:
        # We only use non private tags as keywords may not be unique when
        # there are also private tags present.
        # See also https://github.com/pydicom/pydicom/issues/319
        if elem.tag.is_private:
            continue

        if elem.tag == (0x7FE0, 0x0010):  # discard PixelData
            continue

        if elem.VR == "SQ":
            output[elem.keyword] = [_dictify_dataset(item) for item in elem]
        else:
            v = elem.value

            # We don't use the optional automatic `pydicom.config.datetime_conversion` as
            # it is globally set and we can't use date ranges then anymore for the
            # queries. See https://github.com/pydicom/pydicom/issues/1293
            if elem.VR == "DA":
                v = valuerep.DA(v)
            elif elem.VR == "DT":
                v = valuerep.DT(v)
            elif elem.VR == "TM":
                v = valuerep.TM(v)

            cv = _convert_value(v)

            # An element with a (possible) multiplicity of > 1 should always be returned
            # as list, even with only one element in it (e.g. ModalitiesInStudy)
            vm = dictionary_VM(elem.tag)
            if vm == "1-n" and not isinstance(cv, list):
                cv = [cv]

            output[elem.keyword] = cv

    return output


def _convert_value(v: Any):
    """Converts a pydicom value to native Python value."""
    t = type(v)
    if t in (int, float, type(None)):
        cv = v
    elif t == str:
        cv = _sanitize_unicode(v)
    elif t == bytes:
        cv = _sanitize_unicode(v.decode("ascii", "replace"))
    elif t in (uid.UID, valuerep.PersonName):
        cv = str(v)
    elif t == valuerep.IS:
        cv = int(v)
    elif t == valuerep.DSfloat:
        cv = float(v)
    elif t == valuerep.DA:
        cv = datetime.date.fromisoformat(v.isoformat())
    elif t == valuerep.DT:
        cv = datetime.datetime.fromisoformat(v.isoformat())
    elif t == valuerep.TM:
        cv = datetime.time.fromisoformat(v.isoformat())
    elif t in (valuerep.MultiValue, list):  # pyright: ignore
        cv = [_convert_value(i) for i in v]
    else:
        cv = repr(v)
    return cv


def _sanitize_unicode(s: str):
    return s.replace("\u0000", "").strip()


def _extract_pending_data(results: List[Dict[str, Any]]):
    """Extract the data from a DicomOperation result."""
    status_category = results[-1]["status"]["category"]
    status_code = results[-1]["status"]["code"]
    if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
        raise ValueError(f"{status_category} ({status_code}) occurred during C-FIND.")

    filtered = filter(lambda x: x["status"]["category"] == STATUS_PENDING, results)
    data = map(lambda x: x["data"], filtered)
    return list(data)


def _evaluate_get_move_results(results, query: dict[str, Any]):
    status_category = results[-1]["status"]["category"]
    status_code = results[-1]["status"]["code"]
    if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
        data = results[-1]["data"]
        failed_image_uids = data and data.get("FailedSOPInstanceList")
        error_msg = (
            f"{status_category} ({status_code}) occurred while transferring "
            f"the series with UID {query['SeriesInstanceUID']}."
        )
        if failed_image_uids:
            error_msg += f" Failed images: {', '.join(failed_image_uids)}"
        logger.error(error_msg)
        raise RetriableTaskError(f"Failed to transfer images with status {status_category}.")
