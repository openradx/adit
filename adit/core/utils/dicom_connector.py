"""The heart of ADIT that communicates diretly with the DICOM servers.

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
import logging
import re
from typing import Dict, List, Literal, Union, Any
import time
import datetime
from dataclasses import dataclass
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import errno
from functools import wraps
import pika
from pydicom.dataset import Dataset
from pydicom import dcmread, valuerep, uid
from pydicom.datadict import dictionary_VM
from pydicom.errors import InvalidDicomError
from pynetdicom import (
    AE,
    evt,
    build_role,
    debug_logger,
    BasicWorklistManagementPresentationContexts,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
)

# pylint: disable=no-name-in-module
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelMove,
    EncapsulatedSTLStorage,
    EncapsulatedOBJStorage,
    EncapsulatedMTLStorage,
)

from pynetdicom.status import (
    code_to_category,
    STATUS_PENDING,
    STATUS_SUCCESS,
)
from django.conf import settings
from ..models import DicomServer
from ..errors import RetriableTaskError
from ..utils.sanitize import sanitize_dirname


logger = logging.getLogger(__name__)


def connect_to_server(context: Literal["find", "get", "move", "store"]):
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
                self.open_connection(context)
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
        acse_timeout: int = None
        dimse_timeout: int = None
        network_timeout: int = None

    def __init__(self, server: DicomServer, config: Config = None):
        self.server = server
        if config is None:
            self.config = DicomConnector.Config()
        else:
            self.config = config

        if settings.DICOM_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

        self.assoc = None

    def open_connection(self, command: Literal["find", "get", "move", "store"]):
        if self.assoc:
            raise AssertionError("A former connection was not closed properly.")

        logger.debug("Opening connection to DICOM server %s.", self.server.ae_title)

        for i in range(self.config.connection_retries + 1):
            try:
                self._associate(command)
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

    def find_patients(self, query, limit_results=None):
        if self.server.patient_root_find_support:
            query["QueryRetrieveLevel"] = "PATIENT"
        else:
            query["QueryRetrieveLevel"] = "STUDY"

        patients = self._send_c_find(
            query,
            limit_results=limit_results,
        )

        # Make patients unique, since querying on study level will return all studies for one patient, resulting in duplicate patients
        if query["QueryRetrieveLevel"] == "STUDY":
            seen = set()
            unique_patients = [
                patient
                for patient in patients
                if patient["PatientID"] not in seen
                and not seen.add(patient["PatientID"])
            ]
            patients = unique_patients

        # Some PACS servers (like our Synapse) don't support a query filter of PatientBirthDate
        # as it is optional in the Patient Root Query/Retrieve Information Model,
        # see https://groups.google.com/g/comp.protocols.dicom/c/h28r_znomEw
        # In those cases we we have to filter programmatically.
        # TODO allow range filter (but not needed at the moment)
        birth_date = query.get("PatientBirthDate")
        if birth_date:
            return [
                patient
                for patient in patients
                if patient["PatientBirthDate"] == birth_date
            ]

        return patients

    def find_studies(self, query, limit_results=None):
        query["QueryRetrieveLevel"] = "STUDY"

        if not "NumberOfStudyRelatedInstances" in query:
            query["NumberOfStudyRelatedInstances"] = ""

        studies = self._send_c_find(
            query,
            limit_results=limit_results,
        )
        query_modalities = query.get("ModalitiesInStudy")
        if not query_modalities:
            return studies

        return self._filter_studies_by_modalities(studies, query_modalities)

    def find_series(self, query, limit_results=None):
        """Fetch all series UIDs for a given study UID.

        The series can be filtered by a modality (or a list of modalities for
        multiple modalities). If no modality is set all series of the study
        will be returned.
        """
        query["QueryRetrieveLevel"] = "SERIES"

        # We handle query filter for Modality programmatically because we allow
        # to filter for multiple modalities.
        modality = query.get("Modality")
        if modality:
            query["Modality"] = ""

        series_description = query.get("SeriesDescription")
        if series_description:
            series_description = series_description.lower()
            query["SeriesDescription"] = ""

        series_number = query.get("SeriesNumber")
        if series_number:
            series_number = int(series_number)
            query["SeriesNumber"] = ""

        series_list = self._send_c_find(query, limit_results=limit_results)
        if series_description:
            series_list = list(
                filter(
                    lambda x: re.search(
                        series_description, x["SeriesDescription"].lower()
                    ),
                    series_list,
                )
            )
        if series_number:
            series_list = list(
                filter(
                    lambda x: x["SeriesNumber"] == series_number,
                    series_list,
                )
            )
            for series in series_list:
                series["SeriesNumber"] = str(series["SeriesNumber"])
        if not modality:
            return series_list

        return list(
            filter(
                lambda x: x["Modality"] == modality or x["Modality"] in modality,
                series_list,
            )
        )

    def download_study(  # pylint: disable=too-many-arguments
        self,
        patient_id,
        study_uid,
        folder,
        modality=None,
        modifier_callback=None,
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

            # TODO maybe we should move the series folder name creation to the
            # store handler as it is not guaranteed that all PACS servers
            # do return the SeriesDescription with C-FIND
            series_folder_name = sanitize_dirname(series["SeriesDescription"])
            download_path = Path(folder) / series_folder_name

            self.download_series(
                patient_id, study_uid, series_uid, download_path, modifier_callback
            )

        logger.debug("Successfully downloaded study %s.", study_uid)

    def download_series(  # pylint: disable=too-many-arguments
        self, patient_id, study_uid, series_uid, folder, modifier_callback=None
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
            self._download_series_get(query, folder, modifier_callback)
            logger.debug(
                "Successfully downloaded series %s of study %s.", series_uid, study_uid
            )
        elif (
            self.server.patient_root_move_support or self.server.study_root_move_support
        ):
            self._download_series_move(query, folder, modifier_callback)
            logger.debug(
                "Successfully downloaded series %s of study %s.", series_uid, study_uid
            )
        else:
            raise ValueError(
                "No Query/Retrieve Information Model supported to download images."
            )

    def upload_folder(self, folder):
        """Upload a specified folder to a DICOM server."""

        if not self.server.store_scp_support:
            raise ValueError("Server does not support C-STORE operations.")

        results = self._send_c_store(folder)

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

    def move_study(self, patient_id, study_uid, destination, modality=None):
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

            try:
                self.move_series(patient_id, study_uid, series, destination)
                has_success = True
            except ValueError:
                logger.exception("Failed to move series %s.", series_uid)
                has_failure = True

        if series_list and has_failure:
            if not has_success:
                raise RetriableTaskError("Failed to move all series.")
            raise RetriableTaskError("Failed to move some series.")

    def move_series(self, patient_id, study_uid, series_uid, destination):
        query = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }

        results = self._send_c_move(
            query,
            destination,
        )

        _evaluate_get_move_results(results, query)

    def fetch_study_modalities(self, patient_id, study_uid):
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

    def _associate(self, command: Literal["find", "get", "move", "store"]):
        ae = AE(settings.ADIT_AE_TITLE)

        # We only use the timeouts if set, otherwise we leave the default timeouts
        if self.config.acse_timeout is not None:
            ae.acse_timeout = self.config.acse_timeout
        if self.config.dimse_timeout is not None:
            ae.dimse_timeout = self.config.dimse_timeout
        if self.config.network_timeout is not None:
            ae.network_timeout = self.config.network_timeout

        # Setup the contexts (inspired by https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/apps)
        ext_neg = []
        if command == "find":
            ae.requested_contexts = (
                QueryRetrievePresentationContexts
                + BasicWorklistManagementPresentationContexts
            )
        elif command == "get":
            # We must exclude as many storage contexts as how many query/retrieve contexts we add
            # because the maximum requested contexts is 128. "StoragePresentationContexts" is a list
            # that contains 128 storage contexts itself.
            exclude = [
                EncapsulatedSTLStorage,
                EncapsulatedOBJStorage,
                EncapsulatedMTLStorage,
            ]
            store_contexts = [
                cx
                for cx in StoragePresentationContexts
                if cx.abstract_syntax not in exclude
            ]
            ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
            ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
            for cx in store_contexts:
                ae.add_requested_context(cx.abstract_syntax)
                ext_neg.append(build_role(cx.abstract_syntax, scp_role=True))
        elif command == "move":
            ae.requested_contexts = QueryRetrievePresentationContexts
        elif command == "store":
            ae.requested_contexts = StoragePresentationContexts
        else:
            raise ValueError(
                f"Invalid command type for creating the association: {command}"
            )

        self.assoc = ae.associate(
            self.server.host,
            self.server.port,
            ae_title=self.server.ae_title,
            ext_neg=ext_neg,
        )

        if not self.assoc.is_established:
            logger.error("Could not connect to %s.", self.server)
            raise RetriableTaskError(f"Could not connect to {self.server}.")

    @connect_to_server("find")
    def _send_c_find(
        self,
        query_dict,
        limit_results=None,
        msg_id=1,
    ):
        logger.debug("Sending C-FIND with query: %s", query_dict)

        level = query_dict.get("QueryRetrieveLevel")
        patient_id = _check_required_id(query_dict.get("PatientID"))

        if self.server.study_root_find_support and level != "PATIENT":
            query_model = StudyRootQueryRetrieveInformationModelFind
        elif self.server.patient_root_find_support and (
            level == "PATIENT" or patient_id
        ):
            query_model = PatientRootQueryRetrieveInformationModelFind
        else:
            raise ValueError(
                "No valid Query/Retrieve Information Model for C-FIND could be found."
            )

        query_ds = _make_query_dataset(query_dict)
        responses = self.assoc.send_c_find(query_ds, query_model, msg_id)
        results = self._fetch_results(responses, "C-FIND", query_dict, limit_results)
        return _extract_pending_data(results)

    @connect_to_server("get")
    def _send_c_get(  # pylint: disable=too-many-arguments
        self, query_dict, folder, callback=None, msg_id=1
    ):
        logger.debug("Sending C-GET with query: %s", query_dict)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = _check_required_id(query_dict.get("PatientID"))
        study_uid = _check_required_id(query_dict.get("StudyInstanceUID"))

        if self.server.study_root_get_support and study_uid:
            query_model = StudyRootQueryRetrieveInformationModelGet
        elif self.server.patient_root_get_support and patient_id and study_uid:
            query_model = PatientRootQueryRetrieveInformationModelGet
        else:
            raise ValueError(
                "No valid Query/Retrieve Information Model for C-GET could be selected."
            )

        query_ds = _make_query_dataset(query_dict)
        store_errors = []
        self.assoc.bind(
            evt.EVT_C_STORE, _handle_c_get_store, [folder, callback, store_errors]
        )

        try:
            responses = self.assoc.send_c_get(query_ds, query_model, msg_id)
            results = self._fetch_results(responses, "C-GET", query_dict)
        except Exception as err:
            # Check if an error was triggered by our own store handler due to
            # aborting the assocation.
            if store_errors:
                raise store_errors[0]

            # If not just raise the original error.
            raise err
        finally:
            self.assoc.unbind(evt.EVT_C_STORE, _handle_c_get_store)

        return results

    @connect_to_server("move")
    def _send_c_move(self, query_dict, destination_ae_title, msg_id=1):
        logger.debug("Sending C-MOVE with query: %s", query_dict)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = _check_required_id(query_dict.get("PatientID"))
        study_uid = _check_required_id(query_dict.get("StudyInstanceUID"))

        if self.server.study_root_move_support and study_uid:
            query_model = StudyRootQueryRetrieveInformationModelMove
        elif self.server.patient_root_move_support and patient_id and study_uid:
            query_model = PatientRootQueryRetrieveInformationModelMove
        else:
            raise ValueError(
                "No valid Query/Retrieve Information Model for C-MOVE could be selected."
            )

        query_ds = _make_query_dataset(query_dict)
        responses = self.assoc.send_c_move(
            query_ds, destination_ae_title, query_model, msg_id
        )
        return self._fetch_results(responses, "C-MOVE", query_dict)

    @connect_to_server("store")
    def _send_c_store(self, folder, callback=None, msg_id=1):
        logger.debug("Sending C-STORE of folder: %s", str(folder))

        if not self.server.store_scp_support:
            raise ValueError("C-STORE operation not supported by server.")

        results = []
        for path in Path(folder).rglob("*"):
            if not path.is_file():
                continue

            try:
                ds = dcmread(str(path))
            except InvalidDicomError:
                logger.warning(
                    "Tried to read invalid DICOM file %s. Skipping it.", path
                )
                continue

            # Allow to manipuate the dataset by using a callback before storing to server
            if callback:
                callback(ds)

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
                    folder,
                )
                raise RetriableTaskError(
                    "Connection timed out, was aborted or received invalid "
                    "during C-STORE."
                )

        return results

    def _fetch_results(self, responses, operation, query_dict, limit_results=None):
        results = []
        for (status, identifier) in responses:
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
                    "Connection timed out, was aborted or received invalid "
                    f"during {operation}."
                )
        return results

    # TODO remove pylint disable, see https://github.com/PyCQA/pylint/issues/3882
    # pylint: disable=unsubscriptable-object
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

    def _download_series_get(self, query, folder, modifier_callback=None):
        results = self._send_c_get(query, folder, modifier_callback)

        _evaluate_get_move_results(results, query)

    def _download_series_move(self, query, folder, modifier_callback=None):
        # Fetch all SOPInstanceUIDs in the series so that we can later
        # evaluate if all images were received.
        image_query = dict(
            query, **{"QueryRetrieveLevel": "IMAGE", "SOPInstanceUID": ""}
        )
        images = self._send_c_find(image_query)
        image_uids = [image["SOPInstanceUID"] for image in images]

        # The images are sent to the receiver container (a C-STORE SCP server)
        # by the move operation. Then those are send to a RabbitMQ queue from
        # which we consume them in a separate thread.
        move_stopped_event = threading.Event()
        with ThreadPoolExecutor() as executor:
            future = executor.submit(
                self._consume_dicoms,
                query["StudyInstanceUID"],
                query["SeriesInstanceUID"],
                image_uids,
                folder,
                modifier_callback,
                move_stopped_event,
            )

            try:
                results = self._send_c_move(
                    query,
                    settings.ADIT_AE_TITLE,
                )
                _evaluate_get_move_results(results, query)
            finally:
                move_stopped_event.set()

            # Raises if _consume_dicoms raises
            future.result()

    def _consume_dicoms(  # pylint: disable=too-many-arguments
        self,
        study_uid,
        series_uid,
        image_uids,
        folder,
        modifier_callback,
        move_stopped_event: threading.Event,
    ):
        remaining_image_uids = image_uids[:]

        for message in self._consume_with_timeout(
            study_uid, series_uid, move_stopped_event
        ):
            received_image_uid, data = message

            if received_image_uid in remaining_image_uids:
                ds = dcmread(data)

                if received_image_uid != ds.SOPInstanceUID:
                    raise AssertionError(
                        f"Received wrong image with UID {ds.SOPInstanceUID}. "
                        f"Expected UID {received_image_uid}."
                    )

                if modifier_callback:
                    modifier_callback(ds)

                _save_dicom_from_receiver(ds, folder)

                remaining_image_uids.remove(received_image_uid)

                # Stop if all images of this series were received
                if not remaining_image_uids:
                    break

        if remaining_image_uids:
            if remaining_image_uids == image_uids:
                logger.error("No images of series %s received.", series_uid)
                raise RetriableTaskError("Failed to download all images with C-MOVE.")

            logger.error(
                "These images of series %s were not received: %s",
                series_uid,
                ", ".join(remaining_image_uids),
            )
            raise RetriableTaskError("Failed to download some images with C-MOVE.")

    def _consume_with_timeout(self, study_uid, series_uid, move_stopped_event):
        last_consume_at = time.time()
        for message in self._consume_from_receiver(study_uid, series_uid):
            method, properties, body = message

            # If we are waiting without a message for more then a specified timeout
            # then we stop waiting anymore and also abort an established association
            time_since_last_consume = time.time() - last_consume_at
            timeout = settings.C_MOVE_DOWNLOAD_TIMEOUT
            if time_since_last_consume > timeout:
                logger.error(
                    "C-MOVE download timed out after %d seconds without receiving images.",
                    round(time_since_last_consume),
                )
                if not move_stopped_event.is_set():
                    logger.warning("Aborting not finished C-MOVE operation.")
                    self.abort_connection()

                break

            # We just reached an inactivity timeout
            if not method:
                continue

            # Reset our timer if a real new message arrives
            last_consume_at = time.time()

            received_image_uid = properties.message_id
            data = BytesIO(body)

            yield received_image_uid, data

    def _consume_from_receiver(self, study_uid, series_uid):
        connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
        channel = connection.channel()
        channel.exchange_declare(exchange="received_dicoms", exchange_type="direct")
        result = channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue
        routing_key = f"{self.server.ae_title}\\{study_uid}\\{series_uid}"
        channel.queue_bind(
            exchange="received_dicoms",
            queue=queue_name,
            routing_key=routing_key,
        )

        try:
            yield from channel.consume(queue_name, auto_ack=True, inactivity_timeout=1)
        finally:
            channel.close()
            connection.close()


def _check_required_id(value):
    if value and not "*" in value and not "?" in value:
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
    output = dict()

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
    elif t in (valuerep.MultiValue, list):
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


def _evaluate_get_move_results(results, query):
    status_category = results[-1]["status"]["category"]
    status_code = results[-1]["status"]["code"]
    if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
        data = results[-1]["data"]
        failed_image_uids = data or data.get("FailedSOPInstanceList")
        error_msg = (
            f"{status_category} ({status_code}) occurred while transferring "
            f"the series with UID {query['SeriesInstanceUID']}."
        )
        if failed_image_uids:
            error_msg += f" Failed images: {', '.join(failed_image_uids)}"
        logger.error(error_msg)
        raise RetriableTaskError(
            f"Failed to transfer images with status {status_category}."
        )


def _handle_c_get_store(event, folder, modifier_callback, errors):
    """Handle a C-STORE request event."""

    ds = event.dataset
    context = event.context

    # Add DICOM File Meta Information
    ds.file_meta = event.file_meta

    # Set the transfer syntax attributes of the dataset
    ds.is_little_endian = context.transfer_syntax.is_little_endian
    ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

    folder_path = Path(folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    # Allow to manipuate the dataset by using a callback before saving to disk
    if modifier_callback:
        modifier_callback(ds)

    file_path = folder_path / ds.SOPInstanceUID

    try:
        ds.save_as(str(file_path), write_like_original=False)
    except OSError as err:
        if err.errno == errno.ENOSPC:
            # No space left on destination
            logger.exception("Out of disk space while saving %s.", file_path)
            no_space_error = RetriableTaskError(
                "Out of disk space on destination.", long_delay=True
            )
            no_space_error.__cause__ = err
            errors.append(no_space_error)

            # Unfortunately not all PACS servers support or respect a C-CANCEL request,
            # so we just abort the association.
            # See https://github.com/pydicom/pynetdicom/issues/553
            # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
            event.assoc.abort()

            # Answert with "Out of Resources"
            # see https://pydicom.github.io/pynetdicom/stable/service_classes/defined_procedure_service_class.html
            return 0xA702

    # Return a 'Success' status
    return 0x0000


def _save_dicom_from_receiver(ds, folder):
    folder_path = Path(folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    file_path = folder_path / ds.SOPInstanceUID

    # In this case we don't need to save with `write_like_original=False` as it
    # saved already saved it this way to the buffer in the receiver
    try:
        ds.save_as(str(file_path), write_like_original=False)
    except OSError as err:
        if err.errno == errno.ENOSPC:  # No space left on device
            logger.exception("Out of disk space while saving %s.", file_path)
            raise RetriableTaskError(
                "Out of disk space on destination.", long_delay=True
            ) from err

        raise err
