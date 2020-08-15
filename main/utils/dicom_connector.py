import logging
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import os
from functools import partial
from pydicom.dataset import Dataset
from pydicom import dcmread, valuerep, uid
from pynetdicom import (
    AE,
    evt,
    build_role,
    debug_logger,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION,
)
from pynetdicom.sop_class import (  # pylint: disable-msg=no-name-in-module
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelMove,
)
from pynetdicom.status import code_to_category


def _make_query_dataset(query_dict):
    """Turn a dict into a pydicom dataset for query."""

    ds = Dataset()
    for i in query_dict:
        setattr(ds, i, query_dict[i])
    return ds


def _sanitise_unicode(s):
    return s.replace("\u0000", "").strip()


def _convert_value(v):
    t = type(v)
    if t in (list, int, float):
        cv = v
    elif t == str:
        cv = _sanitise_unicode(v)
    elif t == bytes:
        s = v.decode("ascii", "replace")
        cv = _sanitise_unicode(s)
    elif t == valuerep.DSfloat:
        cv = float(v)
    elif t == valuerep.IS:
        cv = int(v)
    elif t == valuerep.PersonName:
        cv = str(v)
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


def _extract_results(responses, operation, query_dict):
    results = []
    for status, ds in responses:
        if status:
            data = {}
            if ds:
                data.update(_dictify_dataset(ds))

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
            logging.error(
                "Association rejected, aborted or never connected during %s with query: %s.",
                operation,
                str(query_dict),
            )

    return results


def _extract_pending_data(results):
    """Extract the data from a DicomOperation result."""

    filtered = filter(lambda x: x["status"]["category"] == "Pending", results)
    data = map(lambda x: x["data"], filtered)
    return list(data)


def _handle_store(folder, callback, event):
    """Handle a C-STORE request event."""
    ds = event.dataset
    context = event.context

    # Add DICOM File Meta Information
    meta = Dataset()
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
    meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION
    meta.TransferSyntaxUID = context.transfer_syntax
    ds.file_meta = meta

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

    ds.save_as(filename, write_like_original=False)

    # Return a 'Success' status
    return 0x0000


def _connect_to_server(func):
    def wrapper(self, *args, **kwargs):
        if self.assoc is None or not self.assoc.is_alive():
            self.open_connection()

        result = None
        exception_occurred = False
        try:
            result = func(self, *args, **kwargs)
        except Exception as ex:
            logging.error(
                "An error occurred during DICOM operation %s: %s", func.__name__, ex
            )
            exception_occurred = True
        finally:
            if exception_occurred or self.config.auto_close_connection:
                self.close_connection()

        return result

    return wrapper


class DicomConnector:
    @dataclass
    class Config:  # pylint: disable=too-many-instance-attributes
        client_ae_title: str
        server_ae_title: str
        server_ip: str
        server_port: int
        patient_root_query_model_find: bool = True
        patient_root_query_model_get: bool = True
        patient_root_query_model_move: bool = True
        debug: bool = False
        connection_retries: int = 3
        retry_timeout: int = 30  # in seconds
        auto_close_connection = True

    def __init__(self, config: Config):
        self.config = config

        if config.debug:
            debug_logger()

        if config.patient_root_query_model_find:
            self.find_query_model = PatientRootQueryRetrieveInformationModelFind
        else:
            self.find_query_model = StudyRootQueryRetrieveInformationModelFind

        if config.patient_root_query_model_get:
            self.get_query_model = PatientRootQueryRetrieveInformationModelGet
        else:
            self.get_query_model = StudyRootQueryRetrieveInformationModelGet

        if config.patient_root_query_model_move:
            self.move_query_model = PatientRootQueryRetrieveInformationModelMove
        else:
            self.move_query_model = StudyRootQueryRetrieveInformationModelMove

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
            role = build_role(context.abstract_syntax, scp_role=True)
            negotiation_items.append(role)

        self.assoc = ae.associate(
            self.config.server_ip,
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

        for i in range(self.config.connection_retries):
            try:
                self._associate()
                break
            except ConnectionError as err:
                logging.exception("Could not connect to server: %s", str(err))
                if i < self.config.connection_retries - 1:
                    logging.info(
                        "Retrying to connect in %d seconds.", self.config.retry_timeout,
                    )
                    time.sleep(self.config.retry_timeout)
                else:
                    raise err

    def close_connection(self):
        if self.assoc:
            self.assoc.release()
            self.assoc = None

    @_connect_to_server
    def c_find(self, query_dict, msg_id=1):
        query_ds = _make_query_dataset(query_dict)

        responses = self.assoc.send_c_find(query_ds, self.find_query_model, msg_id)
        return _extract_results(responses, "C-Find", query_dict)

    @_connect_to_server
    def c_get(self, query_dict, folder=None, callback=None, msg_id=1):
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)

        ds = _make_query_dataset(query_dict)

        handle_store = partial(_handle_store, folder, callback)
        self.assoc.bind(evt.EVT_C_STORE, handle_store)

        # The Synapse PACS server only accepts study root queries (not patient root queries)
        # for C-GET requests
        responses = self.assoc.send_c_get(ds, self.get_query_model, msg_id)
        results = _extract_results(responses, "C-GET", query_dict)

        self.assoc.unbind(evt.EVT_C_STORE, handle_store)

        return results

    @_connect_to_server
    def c_move(self, query_dict, destination_ae_title, msg_id=1):
        query_ds = _make_query_dataset(query_dict)

        responses = self.assoc.send_c_move(
            query_ds, destination_ae_title, self.move_query_model, msg_id
        )
        return _extract_results(responses, "C-MOVE", query_dict)

    @_connect_to_server
    def c_store(self, folder, callback=None, msg_id=1):
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
                    logging.error(
                        "Invalid connection during C-STORE with folder: %s", folder
                    )

        return results

    def fetch_study_modalities(self, patient_id, study_uid):
        """Fetch all modalities of a study and return them in a list."""

        series_list = self.find_series(patient_id, study_uid)
        modalities = set(map(lambda x: x["Modality"], series_list))
        return sorted(list(modalities))

    def find_patients(self, patient_id, patient_name, patient_birth_date):
        """Find patients with the given patient ID and/or patient name and birth date."""
        query_dict = {
            "QueryRetrieveLevel": "PATIENT",
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
        }
        results = self.c_find(query_dict)
        result_data = _extract_pending_data(results)

        return result_data

    def find_studies(  # pylint: disable=too-many-arguments
        self,
        patient_id="",
        patient_name="",
        patient_birth_date="",
        accession_number="",
        study_date="",
        modality=None,
    ):
        """Find all studies for a given patient and filter optionally by
        study date and/or modality."""

        query_dict = {
            "QueryRetrieveLevel": "STUDY",
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
            "AccessionNumber": accession_number,
            "StudyDate": study_date,
            "StudyTime": "",
            "StudyInstanceUID": "",
            "StudyDescription": "",
        }
        results = self.c_find(query_dict)
        result_data = _extract_pending_data(results)

        for ds in result_data:
            patient_id = ds["PatientID"]
            study_uid = ds["StudyInstanceUID"]
            study_modalities = self.fetch_study_modalities(patient_id, study_uid)
            if modality is not None:
                if isinstance(modality, str):
                    if modality not in study_modalities:
                        continue
                else:
                    # Can also be a list of modalities, TODO but this is not
                    # implemented in the Django BatchTransferRequest model currently
                    if len(set(study_modalities) & set(modality)) == 0:
                        continue

            ds["Modalities"] = study_modalities

        return result_data

    def find_series(self, patient_id, study_uid, modality=None):
        """Find all series UIDs for a given study UID. The series can be filtered by a
        modality (or multiple modalities). If no modality is set all series UIDs of the
        study will be returned."""

        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": "",
            "SeriesDescription": "",
            "Modality": "",
        }
        results = self.c_find(query_dict)
        result_data = _extract_pending_data(results)

        if modality is None:
            return result_data

        return list(
            filter(
                lambda x: x["Modality"] == modality or x["Modality"] in modality,
                result_data,
            )
        )

    def download_patient(  # pylint: disable=too-many-arguments
        self,
        patient_id,
        folder_path,
        modality=None,
        create_series_folders=True,
        modifier_callback=None,
    ):
        study_list = self.find_studies(patient_id, modality=modality)
        for study in study_list:
            study_uid = study["StudyInstanceUID"]
            study_date = study["StudyDate"]
            study_time = study["StudyTime"]
            modalities = ",".join(study["Modalities"])
            study_folder_name = f"{study_date}-{study_time}-{modalities}"
            study_folder_path = Path(folder_path) / study_folder_name

            self.download_study(
                patient_id,
                study_uid,
                study_folder_path,
                modality,
                create_series_folders,
                modifier_callback,
            )

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
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]
            download_path = folder_path
            if create_series_folders:
                series_folder_name = series["SeriesDescription"]
                download_path = Path(folder_path) / series_folder_name

            self.download_series(
                patient_id, study_uid, series_uid, download_path, modifier_callback
            )

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

        if not results or results[-1]["status"]["category"] != "Success":
            msg = str(results)
            raise Exception(
                "Failure while downloading series with UID %s: %s" % (series_uid, msg)
            )

    def upload_folder(self, folder_path):
        """Upload a specified folder to a DICOM server."""

        start_time = datetime.now().ctime()
        logging.info(
            "Upload of folder %s started at %s with config: %s",
            folder_path,
            start_time,
            str(self.config),
        )

        results = self.c_store(folder_path)
        for result in results:
            # Category names can be found in https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/_globals.py
            status_category = result["status"]["category"]
            if status_category != "Success":
                if status_category == "Failure":
                    logging.error(
                        "Error while uploading instance UID %s.", result["data"]
                    )
                else:
                    logging.warning(
                        "%s while uploading instance UID %s.",
                        status_category,
                        result["data"],
                    )
