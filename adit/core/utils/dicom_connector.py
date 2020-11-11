"""The heart of ADIT that communicates diretly with the DICOM servers.

Error handling and logging is quite complex here. All lower level methods
(c_find, c_get, c_move, c_store) only raise a ConnectionError if the connection
itself fails, but not if some operation itself (inside a working connection)
fails. Those failures are recognized and raised in all higher level methods
(find_patients, download_study, ...). A higher level method that uses another
higher level method does catch the exception and raises one itself. Loggings
only occur in higher level methods that uses lower level methods. As logger
the Celery task logger is used as we intercept those messages and save them
in TransferTask model object.
"""
import time
from dataclasses import dataclass
from pathlib import Path
import os
from functools import partial
import errno
from celery.utils.log import get_task_logger
from pydicom.dataset import Dataset
from pydicom import dcmread, valuerep, uid
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
from ..errors import NoSpaceLeftError
from ..utils.sanitize import sanitize_dirname

FORCE_DEBUG_LOGGER = False

# We must use this logger to intercept the logging messages and
# store them in the task (see core.tasks.transfer_dicoms()).
# TODO Maybe it would be better to use the standard python logger somehow.
# See https://www.distributedpython.com/2018/08/28/celery-logging/
# and https://www.distributedpython.com/2018/11/06/celery-task-logger-format/
logger = get_task_logger(__name__)


def _make_query_dataset(query_dict):
    """Turn a dict into a pydicom dataset for query."""

    ds = Dataset()
    for i in query_dict:
        setattr(ds, i, query_dict[i])
    return ds


def _sanitize_unicode(s):
    return s.replace("\u0000", "").strip()


def _convert_value(v):
    t = type(v)
    if t in (list, int, float):
        cv = v
    elif t == str:
        cv = _sanitize_unicode(v)
    elif t == bytes:
        s = v.decode("ascii", "replace")
        cv = _sanitize_unicode(s)
    elif t == valuerep.DSfloat:
        cv = float(v)
    elif t == valuerep.IS:
        cv = int(v)
    elif t == valuerep.PersonName:
        cv = str(v)
    elif t == valuerep.MultiValue:  # e.g. ModalitiesInStudy
        cv = list(v)
    elif t == uid.UID:
        cv = str(v)
    else:
        cv = repr(v)
    return cv


def _dictify_dataset(ds):
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


def _extract_pending_data(results, resource, query_dict):
    """Extract the data from a DicomOperation result."""
    status_category = results[-1]["status"]["category"]
    status_code = results[-1]["status"]["code"]
    if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
        error_msg = f"{status_category} ({status_code}) occurred while trying to find {resource}"
        log_msg = error_msg + " with query params %s and returned identifier: %s"
        logger.error(log_msg, query_dict, results[-1]["data"])
        raise ValueError(error_msg + ".")

    filtered = filter(lambda x: x["status"]["category"] == STATUS_PENDING, results)
    data = map(lambda x: x["data"], filtered)
    return list(data)


def _handle_store(folder, callback, errors, event):
    """Handle a C-STORE request event."""

    ds = event.dataset
    context = event.context

    # Add DICOM File Meta Information
    ds.file_meta = event.file_meta

    # Set the transfer syntax attributes of the dataset
    ds.is_little_endian = context.transfer_syntax.is_little_endian
    ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

    # Save the dataset using the SOP Instance UID as the filename in an optional folder
    filename = ds.SOPInstanceUID
    if folder:
        filename = os.path.join(folder, filename)

    # Allow to manipuate the dataset by using a callback before saving to disk
    if callback:
        callback(ds)

    try:
        ds.save_as(filename, write_like_original=False)
    except OSError as err:
        if err.errno == errno.ENOSPC:  # No space left on device
            logger.exception(
                "No space left to save DICOM dataset to %s. Aborting association.",
                filename,
            )
            errors.append(NoSpaceLeftError())

            # Unfortunately not all PACS servers support or respect a C-CANCEL request,
            # so we just abort the association.
            # See https://github.com/pydicom/pynetdicom/issues/553
            # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
            event.assoc.abort()

            # Out of resources
            # see https://pydicom.github.io/pynetdicom/stable/service_classes/defined_procedure_service_class.html
            return 0xA702

    # Return a 'Success' status
    return 0x0000


def _connect_to_server(func):
    """Automatically handles the connection when `auto_config` option is set.

    Opens and closes the connecition to the DICOM server when a method is
    decorated with this function. Only a connection is opened for the most
    outer function that is called. So if the method itself calls a method
    that is also decorated with this function then the connection is reused
    and the connection is closed by the most outer method automatically.
    """

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
        patient_root_find_support: bool = True
        patient_root_get_support: bool = True
        patient_root_move_support: bool = True
        study_root_find_support: bool = True
        study_root_get_support: bool = True
        study_root_move_support: bool = True
        debug_logger: bool = False
        connection_retries: int = 3
        retry_timeout: int = 30  # in seconds
        auto_connect: bool = True

    def __init__(self, config: Config):
        self.config = config

        if self.config.debug_logger or FORCE_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

        self.default_find_query_model = None
        if self.config.patient_root_find_support:
            self.default_find_query_model = PatientRootQueryRetrieveInformationModelFind
        elif self.config.study_root_find_support:
            self.default_find_query_model = StudyRootQueryRetrieveInformationModelFind

        self.default_get_query_model = None
        if self.config.patient_root_get_support:
            self.default_get_query_model = PatientRootQueryRetrieveInformationModelGet
        elif self.config.study_root_get_support:
            self.default_get_query_model = StudyRootQueryRetrieveInformationModelGet

        self.default_move_query_model = None
        if self.config.patient_root_move_support:
            self.default_move_query_model = PatientRootQueryRetrieveInformationModelMove
        elif self.config.study_root_move_support:
            self.default_move_query_model = StudyRootQueryRetrieveInformationModelMove

        self.assoc = None

    def _associate(self):
        ae = AE(ae_title=self.config.client_ae_title)

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
                "Could not connect to DICOM server with AE Title %s."
                % self.config.server_ae_title
            )

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

    @_connect_to_server
    def c_find(self, query_dict, msg_id=1, limit_results=None, prefer_study_root=False):
        logger.debug("Sending C-FIND with query: %s", query_dict)

        query_ds = _make_query_dataset(query_dict)

        query_model = self.default_find_query_model
        if prefer_study_root and self.config.study_root_find_support:
            query_model = StudyRootQueryRetrieveInformationModelFind
        elif "PatientID" not in query_ds or not query_ds.PatientID:
            if not self.config.study_root_find_support:
                raise ValueError(
                    "Patient ID missing in query without support for "
                    "Study Root Query/Retrieve Information Model."
                )
            query_model = StudyRootQueryRetrieveInformationModelFind

        responses = self.assoc.send_c_find(query_ds, query_model, msg_id)
        return self._fetch_results(responses, "C-FIND", query_dict, limit_results)

    @_connect_to_server
    def c_get(self, query_dict, folder=None, callback=None, msg_id=1):
        logger.debug("Sending C-GET with query: %s", query_dict)

        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)

        query_ds = _make_query_dataset(query_dict)

        query_model = self.default_get_query_model
        if "PatientID" not in query_ds or not query_ds.PatientID:
            if not self.config.study_root_get_support:
                raise ValueError(
                    "Patient ID missing in query without support for "
                    "Study Root Query/Retrieve Information Model."
                )
            query_model = StudyRootQueryRetrieveInformationModelGet

        store_errors = []
        handle_store = partial(_handle_store, folder, callback, store_errors)
        self.assoc.bind(evt.EVT_C_STORE, handle_store)

        try:
            responses = self.assoc.send_c_get(query_ds, query_model, msg_id)
            results = self._fetch_results(responses, "C-GET", query_dict)
        except ConnectionError as err:
            # Check if the connection error was triggered by our own store handler
            # due to aborting the assocation.
            if store_errors:
                raise store_errors[0] from err

            # If not just raise the original error.
            raise err
        finally:
            self.assoc.unbind(evt.EVT_C_STORE, handle_store)

        return results

    @_connect_to_server
    def c_move(self, query_dict, destination_ae_title, msg_id=1):
        logger.debug("Sending C-MOVE with query: %s", query_dict)

        query_ds = _make_query_dataset(query_dict)

        query_model = self.default_move_query_model
        if "PatientID" not in query_ds or not query_ds.PatientID:
            if not self.config.study_root_move_support:
                raise ValueError(
                    "Patient ID missing in query without support for "
                    "Study Root Query/Retrieve Information Model."
                )
            query_model = StudyRootQueryRetrieveInformationModelMove

        responses = self.assoc.send_c_move(
            query_ds, destination_ae_title, query_model, msg_id
        )
        return self._fetch_results(responses, "C-MOVE", query_dict)

    @_connect_to_server
    def c_store(self, folder: Path, callback=None, msg_id=1):
        logger.debug("Sending C-STORE of folder: %s", folder.as_posix())

        results = []
        for root, _, files in os.walk(folder):
            for filename in files:
                filepath = os.path.join(root, filename)
                ds = dcmread(filepath)

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
                            f"response during C-STORE of folder: {folder.as_posix()}"
                        )
                    )

        return results

    @_connect_to_server
    def fetch_study_modalities(self, patient_id, study_uid):
        """Fetch all modalities of a study and return them in a list."""

        try:
            series_list = self.find_series(patient_id, study_uid)
        except ValueError as err:
            raise ValueError(
                "A problem occurred while fetching the study modalities "
                f"of study with UID {study_uid}."
            ) from err

        modalities = set(map(lambda x: x["Modality"], series_list))
        return sorted(list(modalities))

    @_connect_to_server
    def find_patients(self, patient_id="", patient_name="", patient_birth_date=""):
        """Find patients with the given patient ID and/or patient name and birth date."""
        query_dict = {
            "QueryRetrieveLevel": "PATIENT",
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
        }
        results = self.c_find(query_dict)
        patients = _extract_pending_data(results, "patients", query_dict)

        # Some PACS servers (like our Synapse) do simply ignore the PatientBirthDate
        # while querying as it is optional in the Patient Root Query/Retrieve Information Model,
        # see https://groups.google.com/g/comp.protocols.dicom/c/h28r_znomEw
        # So we have to filter programmatically.
        # TODO allow range filter (but not needed at the moment)
        if patient_birth_date:
            return [
                patient
                for patient in patients
                if patient["PatientBirthDate"] == patient_birth_date
            ]

        return patients

    @_connect_to_server
    def find_studies(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        patient_id="",
        patient_name="",
        birth_date="",
        accession_number="",
        study_uid="",
        study_date="",
        study_time="",
        study_description="",
        modality=None,
        limit_results=None,
        prefer_study_root=False,
    ):
        """Find all studies for a given patient and filter optionally by
        study date and/or modality."""

        query_dict = {
            "QueryRetrieveLevel": "STUDY",
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": birth_date,
            "AccessionNumber": accession_number,
            "StudyInstanceUID": study_uid,
            "StudyDate": study_date,
            "StudyTime": study_time,
            "StudyDescription": study_description,
            "NumberOfStudyRelatedInstances": "",
            "ModalitiesInStudy": "",
        }
        results = self.c_find(
            query_dict, limit_results=limit_results, prefer_study_root=prefer_study_root
        )
        studies = _extract_pending_data(results, "studies", query_dict)

        filtered_studies = []
        for study in studies:
            patient_id = study["PatientID"]
            study_uid = study["StudyInstanceUID"]

            # Modalities In Study is not supported by all PACS servers. If it is
            # supported then it should be not empty. Otherwise we fetch the Modality
            # of all its series manually.
            if study["ModalitiesInStudy"]:
                study_modalities = study["ModalitiesInStudy"]
            else:
                try:
                    study_modalities = self.fetch_study_modalities(
                        patient_id, study_uid
                    )
                except ValueError as err:
                    raise ValueError(
                        "Failed to fetch modalities of study with UID %s" % study_uid
                    ) from err

            study["Modalities"] = study_modalities

            if modality:
                if isinstance(modality, str):
                    if modality not in study_modalities:
                        continue
                else:
                    # Can also be a list of modalities, TODO but this is not
                    # implemented in the Django BatchTransferRequest model currently
                    if len(set(study_modalities) & set(modality)) == 0:
                        continue

            filtered_studies.append(study)

        return filtered_studies

    @_connect_to_server
    def find_series(  # pylint: disable=too-many-arguments
        self,
        patient_id="",
        study_uid="",
        series_uid="",
        series_description="",
        modality=None,
    ):
        """Find all series UIDs for a given study UID.

        The series can be filtered by a modality (or a list of modalities for
        multiple modalities). If no modality is set all series UIDs of the study
        will be returned.
        """
        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
            "SeriesDescription": series_description,
            "Modality": "",  # we handle Modality programmatically, see below
        }
        results = self.c_find(query_dict)
        series_list = _extract_pending_data(results, "series", query_dict)

        if modality is None:
            return series_list

        return list(
            filter(
                lambda x: x["Modality"] == modality or x["Modality"] in modality,
                series_list,
            )
        )

    @_connect_to_server
    def download_patient(  # pylint: disable=too-many-arguments
        self,
        patient_id,
        folder_path,
        modality=None,
        create_series_folders=True,
        modifier_callback=None,
    ):
        studies = self.find_studies(patient_id, modality=modality)

        failed_studies = []
        for study in studies:
            study_uid = study["StudyInstanceUID"]
            study_date = study["StudyDate"]
            study_time = study["StudyTime"]
            modalities = ",".join(study["Modalities"])
            study_folder_name = f"{study_date}-{study_time}-{modalities}"
            study_folder_path = Path(folder_path) / study_folder_name

            try:
                self.download_study(
                    patient_id,
                    study_uid,
                    study_folder_path,
                    modality,
                    create_series_folders,
                    modifier_callback,
                )
            except ValueError:
                failed_studies.append(study_uid)

        if len(failed_studies) > 0:
            raise ValueError(
                "Problems occurred while downloading studies with UID: %s"
                % ", ".join(failed_studies)
            )

    @_connect_to_server
    def download_study(  # pylint: disable=too-many-arguments
        self,
        patient_id,
        study_uid,
        folder_path,
        modality=None,
        create_series_folders=True,
        modifier_callback=None,
    ):
        series_list = self.find_series(patient_id, study_uid, modality)

        failed_series = []
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]
            download_path = folder_path
            if create_series_folders:
                series_folder_name = sanitize_dirname(series["SeriesDescription"])
                download_path = Path(folder_path) / series_folder_name

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

    @_connect_to_server
    def download_series(  # pylint: disable=too-many-arguments
        self, patient_id, study_uid, series_uid, folder_path, modifier_callback=None
    ):
        """Download all series to a specified folder for given series UIDs and pseudonymize
        the dataset before storing it to disk."""

        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }

        results = self.c_get(query_dict, folder_path, modifier_callback)

        status_category = results[-1]["status"]["category"]
        status_code = results[-1]["status"]["code"]
        if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
            error_msg = (
                f"{status_category} ({status_code}) occurred while downloading "
                f"series with UID {series_uid}."
            )
            log_msg = error_msg + " Provided identifier: %s"
            logger.error(log_msg, results[-1]["data"])
            raise ValueError(error_msg)

    @_connect_to_server
    def upload_folder(self, folder_path):
        """Upload a specified folder to a DICOM server."""

        results = self.c_store(folder_path)

        failed_instances = []
        for result in results:
            status_category = result["status"]["category"]
            status_code = result["status"]["code"]
            instance_uid = result["data"]["SOPInstanceUID"]
            if status_category != STATUS_SUCCESS:
                failed_instances.append(instance_uid)
                logger.error(
                    "%s (%d) occurred during uploading instance with UID %s.",
                    status_category,
                    status_code,
                    instance_uid,
                )

        if len(failed_instances) > 0:
            raise ValueError(
                "Problems occurred while uploading instances with UID: %s"
                % ", ".join(failed_instances)
            )
