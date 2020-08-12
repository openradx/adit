import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from .dicom_operations import (
    DicomFind,
    DicomGet,
    DicomStore,
    DicomOperationConfig,
)


class DicomHandler:

    SUCCESS = "Success"
    FAILURE = "Failure"

    @dataclass
    class Config:  # pylint: disable=too-many-instance-attributes
        username: str
        client_ae_title: str
        source_ae_title: str
        source_ip: str
        source_port: int
        destination_ae_title: str = None
        destination_ip: str = None
        destination_port: int = None
        destination_folder: str = None
        patient_root_query_model_find: bool = True
        patient_root_query_model_get: bool = True
        debug: bool = False

    def __init__(self, config: Config):
        self.config = config

        self._find = DicomFind(
            DicomOperationConfig(
                client_ae_title=config.client_ae_title,
                server_ae_title=config.source_ae_title,
                server_ip=config.source_ip,
                server_port=config.source_port,
                patient_root_query_model=config.patient_root_query_model_find,
                debug=config.debug,
            )
        )
        self._get = DicomGet(
            DicomOperationConfig(
                client_ae_title=config.client_ae_title,
                server_ae_title=config.source_ae_title,
                server_ip=config.source_ip,
                server_port=config.source_port,
                patient_root_query_model=config.patient_root_query_model_get,
                debug=config.debug,
            )
        )
        self._store = DicomStore(
            DicomOperationConfig(
                client_ae_title=config.client_ae_title,
                server_ae_title=config.destination_ae_title,
                server_ip=config.destination_ip,
                server_port=config.destination_port,
                debug=config.debug,
            )
        )

    def _extract_pending_data(self, results):  # pylint: disable=no-self-use
        """Extract the data from a DicomOperation result."""

        filtered = filter(lambda x: x["status"]["category"] == "Pending", results)
        data = map(lambda x: x["data"], filtered)
        return list(data)

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
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

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
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

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
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

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

        results = self._get.send_c_get(query_dict, folder_path, modifier_callback)

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

        results = self._store.send_c_store(folder_path)
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
