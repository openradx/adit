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
from typing import Dict, List, Union, Any
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
from celery.utils.log import get_task_logger
from pydicom import config as pydicom_config
from pydicom.dataset import Dataset
from pydicom import dcmread, valuerep, uid
from pydicom.errors import InvalidDicomError
from pynetdicom import (
    AE,
    evt,
    build_role,
    debug_logger,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
)
from pynetdicom.sop_class import (  # pylint: disable-msg=no-name-in-module
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelMove,
)
from pynetdicom.status import (
    code_to_category,
    STATUS_PENDING,
    STATUS_SUCCESS,
)
from ..utils.sanitize import sanitize_dirname

FORCE_DEBUG_LOGGER = False

# We must use this logger to intercept the logging messages and
# store them in the task (see core.tasks.transfer_dicoms()).
# TODO Maybe it would be better to use the standard python logger somehow.
# See https://www.distributedpython.com/2018/08/28/celery-logging/
# and https://www.distributedpython.com/2018/11/06/celery-task-logger-format/
logger = get_task_logger(__name__)

pydicom_config.datetime_conversion = True


def connect_to_server(func):
    """Automatically handles the connection when `auto_config` option is set.

    Opens and closes the connecition to the DICOM server when a method is
    decorated with this function. Only a connection is opened for the most
    outer function that is called. So if the method itself calls a method
    that is also decorated with this function then the connection is reused
    and the connection is closed by the most outer method automatically.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        opened_connection = False

        is_connected = self.assoc and self.assoc.is_alive()
        if self.config.auto_connect and not is_connected:
            self.open_connection()
            opened_connection = True

        result = func(self, *args, **kwargs)

        if opened_connection and self.config.auto_connect:
            self.close_connection()
            opened_connection = False

        return result

    return wrapper


class DicomConnector:
    @dataclass
    class Config:  # pylint: disable=too-many-instance-attributes
        client_ae_title: str
        server_ae_title: str
        server_host: str
        server_port: int
        rabbitmq_url: str = None
        patient_root_find_support: bool = True
        patient_root_get_support: bool = True
        patient_root_move_support: bool = True
        study_root_find_support: bool = True
        study_root_get_support: bool = True
        study_root_move_support: bool = True
        debug_logger: bool = False
        auto_connect: bool = True
        connection_retries: int = 3
        retry_timeout: int = 30  # in seconds
        acse_timeout: int = None
        dimse_timeout: int = None
        network_timeout: int = None

    def __init__(self, config: Config):
        self.config = config

        if self.config.debug_logger or FORCE_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

        self.assoc = None

    def open_connection(self):
        if self.assoc:
            raise AssertionError("A former connection was not closed properly.")

        logger.debug(
            "Opening connection to DICOM server %s.", self.config.server_ae_title
        )

        for i in range(self.config.connection_retries):
            try:
                self._associate()
                break
            except ConnectionError as err:
                logger.exception("Could not connect to server: %s", str(err))
                if i < self.config.connection_retries - 1:
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

        logger.debug(
            "Closing connection to DICOM server %s.", self.config.server_ae_title
        )

        self.assoc.release()
        self.assoc = None

    def abort_connection(self):
        if self.assoc and self.assoc.is_alive():
            self.assoc.abort()

    @connect_to_server
    def find_patients(self, query, limit_results=None):
        query["QueryRetrieveLevel"] = "PATIENT"

        if not self.config.patient_root_find_support:
            raise ValueError(
                "Searching for patients is not supported without C-FIND support for "
                "Patient Root Query/Retrieve Information Model."
            )

        patients = self.c_find(
            query,
            PatientRootQueryRetrieveInformationModelFind,
            limit_results=limit_results,
        )

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

    @connect_to_server
    def find_studies(self, query, force_study_root=False, limit_results=None):
        query["QueryRetrieveLevel"] = "STUDY"

        if not "NumberOfStudyRelatedInstances" in query:
            query["NumberOfStudyRelatedInstances"] = ""

        studies = self.c_find(
            query,
            self._select_query_model_find(query, force_study_root=force_study_root),
            limit_results=limit_results,
        )

        # When a study only contains one modality then ModalitiesInStudy returns a
        # string, otherwise a list. To make it consistent we convert everything
        # to a list. TODO check if this is a bug in pydicom
        for study in studies:
            modalities = study.get("ModalitiesInStudy")
            if modalities and isinstance(modalities, str):
                study["ModalitiesInStudy"] = [modalities]

        query_modalities = query.get("ModalitiesInStudy")
        if not query_modalities:
            return studies

        return self._filter_studies_by_modalities(studies, query_modalities)

    @connect_to_server
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

        series_list = self.c_find(
            query, self._select_query_model_find(query), limit_results=limit_results
        )

        if not modality:
            return series_list

        return list(
            filter(
                lambda x: x["Modality"] == modality or x["Modality"] in modality,
                series_list,
            )
        )

    @connect_to_server
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
            }
        )

        failed_series = []
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            # TODO maybe we should move the series folder name creation to the
            # store handler as it is not guaranteed that all PACS servers
            # do return the SeriesDescription with C-FIND
            series_folder_name = sanitize_dirname(series["SeriesDescription"])
            download_path = Path(folder) / series_folder_name

            try:
                self.download_series(
                    patient_id, study_uid, series_uid, download_path, modifier_callback
                )
            except ValueError:
                failed_series.append(series_uid)

        if len(failed_series) > 0:
            raise ValueError(
                "Problems occurred while downloading series with UID: %s"
                % ", ".join(failed_series)
            )

    @connect_to_server
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

        if self.config.patient_root_get_support or self.config.study_root_get_support:
            self._download_series_get(query, folder, modifier_callback)
        elif (
            self.config.patient_root_move_support or self.config.study_root_move_support
        ):
            self._download_series_move(query, folder, modifier_callback)
        else:
            raise ValueError(
                "No Query/Retrieve Information Model supported to download images."
            )

    @connect_to_server
    def upload_folder(self, folder):
        """Upload a specified folder to a DICOM server."""

        results = self.c_store(folder)

        failed = []
        for result in results:
            status_category = result["status"]["category"]
            status_code = result["status"]["code"]
            image_uid = result["data"]["SOPInstanceUID"]
            if status_category != STATUS_SUCCESS:
                failed.append((image_uid, status_category, status_code))

        if failed:
            failed = [f"{i[0]} ({i[1]} {i[2]}" for i in failed]
            raise ValueError(
                "Problems while uploading the following images: %s" % ", ".join(failed)
            )

    @connect_to_server
    def c_find(
        self,
        query_dict,
        query_model,
        limit_results=None,
        msg_id=1,
    ):
        logger.debug("Sending C-FIND with query: %s", query_dict)
        query_ds = _make_query_dataset(query_dict)
        responses = self.assoc.send_c_find(query_ds, query_model, msg_id)
        results = self._fetch_results(responses, "C-FIND", query_dict, limit_results)
        return _extract_pending_data(results)

    @connect_to_server
    def c_get(  # pylint: disable=too-many-arguments
        self, query_dict, query_model, folder, callback=None, msg_id=1
    ):
        logger.debug("Sending C-GET with query: %s", query_dict)
        query_ds = _make_query_dataset(query_dict)
        store_errors = []
        self.assoc.bind(
            evt.EVT_C_STORE, _handle_c_get_store, [folder, callback, store_errors]
        )

        try:
            responses = self.assoc.send_c_get(query_ds, query_model, msg_id)
            results = self._fetch_results(responses, "C-GET", query_dict)
        except ConnectionError as err:
            # Check if the connection error was triggered by our own store handler
            # due to aborting the assocation.
            if store_errors:
                raise store_errors[0]

            # If not just raise the original error.
            raise err
        finally:
            self.assoc.unbind(evt.EVT_C_STORE, _handle_c_get_store)

        return results

    @connect_to_server
    def c_move(self, query_dict, query_model, destination_ae_title, msg_id=1):
        logger.debug("Sending C-MOVE with query: %s", query_dict)
        query_ds = _make_query_dataset(query_dict)
        responses = self.assoc.send_c_move(
            query_ds, destination_ae_title, query_model, msg_id
        )
        return self._fetch_results(responses, "C-MOVE", query_dict)

    @connect_to_server
    def c_store(self, folder, callback=None, msg_id=1):
        logger.debug("Sending C-STORE of folder: %s", str(folder))

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
                raise ConnectionError(
                    (
                        "Connection timed out, was aborted or received invalid "
                        f"response during C-STORE of folder: {folder}"
                    )
                )

        return results

    @connect_to_server
    def fetch_study_modalities(self, patient_id, study_uid):
        """Fetch all modalities of a study and return them in a list."""

        try:
            series_list = self.find_series(
                {"PatientID": patient_id, "StudyInstanceUID": study_uid, "Modality": ""}
            )
        except ValueError as err:
            raise ValueError(
                "A problem occurred while fetching the study modalities "
                f"of study with UID {study_uid}."
            ) from err

        modalities = set(map(lambda x: x["Modality"], series_list))
        return sorted(list(modalities))

    def _associate(self):
        ae = AE(ae_title=self.config.client_ae_title)

        if self.config.acse_timeout is not None:
            ae.acse_timeout = self.config.acse_timeout

        if self.config.dimse_timeout is not None:
            ae.dimse_timeout = self.config.dimse_timeout

        if self.config.network_timeout is not None:
            ae.network_timeout = self.config.network_timeout

        # See https://github.com/pydicom/pynetdicom/issues/459
        # and https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/apps/getscu/getscu.py#L222
        cx = list(QueryRetrievePresentationContexts)
        nr_pc = len(QueryRetrievePresentationContexts)
        cx += StoragePresentationContexts[: 128 - nr_pc]
        ae.requested_contexts = cx
        negotiation_items = []
        for context in StoragePresentationContexts[: 128 - nr_pc]:
            role = build_role(context.abstract_syntax, scp_role=True, scu_role=True)
            negotiation_items.append(role)

        self.assoc = ae.associate(
            self.config.server_host,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
            ext_neg=negotiation_items,
        )

        if not self.assoc.is_established:
            raise ConnectionError(
                "Could not connect to DICOM server ["
                f"AET {self.config.server_ae_title}, "
                f"IP {self.config.server_host}, "
                f"Port {self.config.server_port}]"
            )

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
                raise ConnectionError(
                    (
                        "Connection timed out, was aborted or received invalid "
                        f"response during {operation} with query: {str(query_dict)}"
                    )
                )
        return results

    def _select_query_model_find(self, query, force_study_root=False):
        if force_study_root:
            if not self.config.study_root_find_support:
                raise ValueError(
                    "Missing support for Study Root Query/Retrieve Information Model."
                )
            return StudyRootQueryRetrieveInformationModelFind

        # If not Study Root Query/Retrieve Information Model is forced we prefer
        # Patient Root Query/Retrieve Information Model, but a Patient ID # (without wildcards)
        # must be present
        patient_id = query.get("PatientID")
        patient_id_valid = (
            patient_id and not "*" in patient_id and not "?" in patient_id
        )
        if patient_id_valid and self.config.patient_root_find_support:
            return PatientRootQueryRetrieveInformationModelFind

        if self.config.study_root_find_support:
            return StudyRootQueryRetrieveInformationModelFind

        raise ValueError(
            "No valid Query/Retrieve Information Model for C-FIND could be found."
        )

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
        results = self.c_get(
            query, self._select_query_model_get(query), folder, modifier_callback
        )

        _evaluate_get_move_results(results, query)

    def _select_query_model_get(self, query):
        if query["PatientID"] and self.config.patient_root_get_support:
            return PatientRootQueryRetrieveInformationModelGet

        if query["StudyInstanceUID"] and self.config.study_root_get_support:
            return StudyRootQueryRetrieveInformationModelGet

        raise ValueError(
            "No valid Query/Retrieve Information Model for C-GET could be selected."
        )

    def _download_series_move(self, query, folder, modifier_callback=None):
        # Fetch all SOPInstanceUIDs in the series so that we can later
        # evaluate if all images were received.
        image_query = dict(
            query, **{"QueryRetrieveLevel": "IMAGE", "SOPInstanceUID": ""}
        )
        images = self.c_find(image_query, self._select_query_model_find(image_query))
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

            results = self.c_move(
                query,
                self._select_query_model_move(query),
                self.config.client_ae_title,
            )

            move_stopped_event.set()

            future.result()

            _evaluate_get_move_results(results, query)

    def _select_query_model_move(self, query):
        if query["PatientID"] and self.config.patient_root_move_support:
            return PatientRootQueryRetrieveInformationModelMove

        if query["StudyInstanceUID"] and self.config.study_root_move_support:
            return StudyRootQueryRetrieveInformationModelMove

        raise ValueError(
            "No valid Query/Retrieve Information Model for C-MOVE could be selected."
        )

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

                self._save_dicom_from_receiver(ds, folder)

                remaining_image_uids.remove(received_image_uid)

                # Stop if all images of this series were received
                if not remaining_image_uids:
                    break

        if remaining_image_uids:
            if remaining_image_uids == image_uids:
                raise ValueError(f"No images of series with UID {series_uid} received.")
            raise ValueError(
                f"Several images of series with UID {series_uid} were not received: "
                f"{remaining_image_uids}"
            )

    def _consume_with_timeout(self, study_uid, series_uid, move_stopped_event):
        last_consume_at = time.time()
        for message in self._consume_from_receiver(study_uid, series_uid):
            method, properties, body = message

            # If we are waiting without a message for more than 60s
            # after the move operation stopped then stop waiting anymore
            time_since_last_consume = time.time() - last_consume_at
            if move_stopped_event.is_set() and time_since_last_consume > 60:
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
        connection = pika.BlockingConnection(
            pika.URLParameters(self.config.rabbitmq_url)
        )
        channel = connection.channel()
        channel.exchange_declare(exchange="received_dicoms", exchange_type="direct")
        result = channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue
        routing_key = f"{self.config.server_ae_title}\\{study_uid}\\{series_uid}"
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

    def _save_dicom_from_receiver(self, ds, folder):
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)

        file_path = folder_path / ds.SOPInstanceUID

        # In this case we don't need to save with `write_like_original=False` as it
        # saved already saved it this way to the buffer in the receiver
        try:
            ds.save_as(str(file_path), write_like_original=False)
        except OSError as err:
            if err.errno == errno.ENOSPC:  # No space left on device
                raise IOError(f"Out of disk space while saving {file_path}.") from err

    @connect_to_server
    def _send_study(self, patient_id, study_uid, destination, modality=None):
        series_list = self.find_series(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "Modality": modality,
                "SeriesInstanceUID": "",
                "SeriesDescription": "",
            }
        )

        failed_series = []
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            try:
                self._send_series(patient_id, study_uid, series, destination)
            except ValueError:
                failed_series.append(series_uid)

        if len(failed_series) > 0:
            raise ValueError(
                "Problems occurred while sending series with UID: %s"
                % ", ".join(failed_series)
            )

    @connect_to_server
    def _send_series(self, patient_id, study_uid, series_uid, destination):
        query = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }

        results = self.c_move(
            query,
            self._select_query_model_move(query),
            destination,
        )

        _evaluate_get_move_results(results, query)


def _make_query_dataset(query_dict: Dict[str, Any]):
    """Turn a dict into a pydicom dataset for query."""

    ds = Dataset()
    for i in query_dict:
        setattr(ds, i, query_dict[i])
    return ds


def _sanitize_unicode(s: str):
    return s.replace("\u0000", "").strip()


def _convert_value(v: Any):
    """Converts a pydicom value to native Python value.

    Only works with date, time and datetime conversion when
    pydicom.conf.datetime_conversion is set to True.
    """
    t = type(v)
    if t in (list, int, float, type(None)):
        cv = v
    elif t == str:
        cv = _sanitize_unicode(v)
    elif t == bytes:
        s = v.decode("ascii", "replace")
        cv = _sanitize_unicode(s)
    elif t == uid.UID:
        cv = str(v)
    elif t == valuerep.IS:
        cv = int(v)
    elif t == valuerep.DSfloat:
        cv = float(v)
    elif t == valuerep.PersonName:
        cv = str(v)
    elif t == valuerep.MultiValue:  # e.g. ModalitiesInStudy
        cv = list(v)
    elif t == valuerep.DA:
        cv = datetime.date.fromisoformat(v.isoformat())
    elif t == valuerep.TM:
        cv = datetime.time.fromisoformat(v.isoformat())
    elif t == valuerep.DT:
        cv = datetime.datetime.fromisoformat(v.isoformat())
    else:
        cv = repr(v)
    return cv


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

        if elem.VR != "SQ":
            output[elem.keyword] = _convert_value(elem.value)
        else:
            output[elem.keyword] = [_dictify_dataset(item) for item in elem]

    return output


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
        raise ValueError(error_msg)


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
        if err.errno == errno.ENOSPC:  # No space left on device
            no_space_error = IOError(f"Out of disk space while saving {file_path}.")
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
