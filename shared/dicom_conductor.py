import logging
from dataclasses import dataclass
from datetime import datetime
import tempfile
import shutil
import os
import subprocess
from pathlib import Path
from functools import partial
from .tools import Anonymizer
from .dicom_operations import (
    Config as OpConfig,
    DicomFind, DicomGet, DicomStore
)

@dataclass
class Config:
    username: str
    client_ae_title: str
    cache_folder: str
    source_ip: str
    source_port: int
    source_ae_title: str
    target_ip: str = ""
    target_port: int = 0
    target_ae_title: str = ""
    archive_folder: str = ""
    archive_name: str = ""
    trial_name: str = ""
    include_structured_reports: bool = False
    pseudonymize: bool = True
    cleanup: bool = True

class ProcessingError(Exception):
    pass


class DicomConductor:
    """A higher level executor that uses lower level operations to transfer
    DICOM datasets from one server to another or to export them in an archive
    on a specified drive.
    Works with data as provided by tools.ExcelProcessor."""

    SUCCESS = "Success"
    INFO = "Info"
    ERROR = "Error"

    def __init__(self, config):
        self._config = config
        self.patient_id_cache = dict()
        self.pseudonym_cache = dict()
        self._anonymizer = Anonymizer()
        self._find = DicomFind(OpConfig(
            self._config.client_ae_title,
            self._config.source_ip,
            self._config.source_port,
            self._config.source_ae_title
        ))
        self._get = DicomGet(OpConfig(
            self._config.client_ae_title,
            self._config.source_ip,
            self._config.source_port,
            self._config.source_ae_title,
            patient_root_query_model=False
        ))
        self._store = DicomStore(OpConfig(
            self._config.client_ae_title,
            self._config.target_ip,
            self._config.target_port,
            self._config.target_ae_title
        ))

    def fetch_patient_ids(self, data, result_callback):
        """Fetch the patient IDs for a given dataset in the PACS"""
        
        for patient in data:
            if patient['PatientID'].strip():
                result_callback({
                    'RowID': patient['RowID'],
                    'PatientID': patient['PatientID'],
                    'Status': DicomConductor.INFO,
                    'Message': "Patient ID already present"
                })
            else:
                try:
                    patient_id = self._find_patient_id(patient['PatientName'], patient['PatientBirthDate'])
                    result_callback({
                        'RowID': patient['RowID'],
                        'Status': DicomConductor.SUCCESS,
                        'Message': patient_id
                    })
                except ProcessingError as err:
                    result_callback({
                        'RowID': patient['RowID'],
                        'Status': DicomConductor.ERROR,
                        'Message': str(err)
                    })

    def download(self, data, archive_password, result_callback):
        start_time = datetime.now().ctime()
        logging.info("Download of %d patients started at %s with config: %s" %
            (len(data), start_time, str(self._config)))

        temp_folder = tempfile.mkdtemp(dir=self._config.cache_folder)

        self._create_archive(temp_folder, start_time, archive_password)

        self._fetch_studies(
            data,
            temp_folder,
            lambda patient_folder: self._add_to_archive(patient_folder, archive_password),
            result_callback
        )

    def transfer(self, data, result_callback):
        start_time = datetime.now().ctime()
        logging.info("Transfer of %d patients started at %s with config: %s" %
            (len(data), start_time, str(self._config)))

        temp_folder = tempfile.mkdtemp(dir=self._config.cache_folder)

        self._fetch_studies(
            data,
            temp_folder,
            lambda patient_folder: self.upload_folder(patient_folder),
            result_callback
        )

    def upload_folder(self, folder_path):
        """Upload a specified folder to a DICOM server."""

        start_time = datetime.now().ctime()
        logging.info("Upload of folder %s started at %s with config: %s" %
            (folder_path, start_time, str(self._config)))

        results = self._store.send_c_store(folder_path)
        for result in results:
            # Category names can be found in https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/_globals.py
            status_category = result['status']['category']
            if status_category != "Success":
                if status_category == "Failure":
                    logging.error("Error while uploading instance UID %s." % result['data'])
                else:
                    logging.warning("%s while uploading instance UID %s." % (status_category, result['data']))

    def _fetch_studies(
        self,
        study_data,
        temp_folder,
        handler_callback,
        result_callback
    ):
        """Downloads the DICOM instances of specified studys to a temporary folder, calls a provided handler
        to use those downloaded files somehow and deletes them afterwards.
        By default the DICOM instances are pseudonymized."""

        for study in study_data:
            row_id = study['RowID']
            patient_id = study['PatientID'].strip()

            try:
                if not patient_id:
                    # Try to resolve patient ID if only name and birth date is given
                    patient_name = study['PatientName']
                    patient_birth_date = study['PatientBirthDate']
                    patient_id = self._find_patient_id(patient_name, patient_birth_date)

                # Only works ok when a provided pseudonym in the Excel file is assigned to the same patient 
                # in the whole file. Never mix provided pseudonym with not filled out pseudonym for the
                # same patient.
                if self._config.pseudonymize:
                    pseudonym = study['Pseudonym'].strip()
                    if not pseudonym:
                        pseudonym = self.pseudonym_cache.get(patient_id)
                    if not pseudonym:
                        pseudonym = self._anonymizer.generate_pseudonym()
                        self.pseudonym_cache[patient_id] = pseudonym
                    patient_folder = os.path.join(temp_folder, pseudonym)
                else:
                    pseudonym = None
                    patient_folder = os.path.join(temp_folder, patient_id)

                if not os.path.exists(patient_folder):
                    Path(patient_folder).mkdir()

                study_date = study['StudyDate']
                modality = study['Modality']
                self._download_study(patient_id, study_date, modality, pseudonym, patient_folder)

                handler_callback(patient_folder)

                # If no exception occurred then transfer succeeded
                logging.info("Successfully processed study in row %d." % row_id)
                result_callback({
                    'RowID': row_id,
                    'Status': DicomConductor.SUCCESS,
                    'Message': pseudonym if pseudonym else "",
                })

            except ProcessingError as err:
                logging.error("Error while processing study in row %d: %s" % (row_id, str(err)))
                result_callback({
                    'RowID': row_id,
                    'Status': DicomConductor.ERROR,
                    'Message': str(err)
                })

            finally:
                if self._config.cleanup:
                    shutil.rmtree(patient_folder)

        if self._config.cleanup:
            shutil.rmtree(temp_folder)

        logging.info("Transfer finished at %s." % datetime.now().ctime())

    def _extract_pending_data(self, results):
        """Extract the data from a DicomOperation result."""

        filtered = filter(lambda x: x['status']['category'] == 'Pending', results)
        data = map(lambda x: x['data'], filtered)
        return data

    def _find_patient_id(self, patient_name, patient_birth_date):
        """Find the patient ID for a given name and birth date in the pacs."""

        patient_id_key = f"{patient_name}__{patient_birth_date}"
        if patient_id_key in self.patient_id_cache:
            return self.patient_id_cache[patient_id_key]

        query_dict = {
            "QueryRetrieveLevel": "PATIENT",
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
            "PatientID": ""
        }
        results = self._find.send_c_find(query_dict)

        patient_id = None
        # Unfortunately we have to compare the birthdate ourself as the Synapse PACS server
        # ignores the PatientBirthDate query itself.
        patients = self._extract_pending_data(results)
        for patient in patients:
            if ("PatientBirthDate" in patient and 
                    patient["PatientBirthDate"] == query_dict["PatientBirthDate"]):
                if patient_id is not None:
                    raise ProcessingError("Non disctinct Patient ID.")
                patient_id = patient["PatientID"]

        if not patient_id:
            raise ProcessingError("No Patient ID found.")

        self.patient_id_cache[patient_id_key] = patient_id
        
        return patient_id

    def _find_study_uids(self, patient_id, study_date):
        """Find all study UIDs for a given patient on a given date."""

        query_dict = {
            "QueryRetrieveLevel": "STUDY",
            "PatientID": patient_id,
            "StudyInstanceUID": ""
        }
        if study_date:
            query_dict["StudyDate"] = study_date

        results = self._find.send_c_find(query_dict)
        data = self._extract_pending_data(results)

        study_uids = []
        for study_uid in map(lambda x: x['StudyInstanceUID'], data):
            study_uids.append(study_uid)

        if not study_uids:
            raise ProcessingError("No study on date %s." % study_date)

        return study_uids

    def _find_series_uids(self, patient_id, study_uid, modality):
        """Find all series UIDs for a given patient, study UID and modalilities."""

        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": "",
            "Modality": ""
        }
        results = self._find.send_c_find(query_dict)
        data = self._extract_pending_data(results)

        structured_reports = []
        series_uids = []
        for series in data:
            if series['Modality'] == 'SR':
                structured_reports.append(series['SeriesInstanceUID'])
            if series['Modality'] == modality:
                series_uids.append(series['SeriesInstanceUID'])

        if series_uids and self._config.include_structured_reports:
            series_uids += structured_reports

        return series_uids

    def _download_study(self, patient_id, study_date, modality, pseudonym, patient_folder):
        study_uids = self._find_study_uids(patient_id, study_date)

        study_counter = 1
        for study_uid in study_uids:
            series_uids = self._find_series_uids(patient_id, study_uid, modality)

            if series_uids:
                study_folder_name = study_date
                if study_counter > 1:
                    study_folder_name += "_" + study_counter
                study_folder = os.path.join(patient_folder, study_folder_name)
                self._download_series(patient_id, study_uid, series_uids, pseudonym, study_folder)
                study_counter += 1
                
        if study_counter == 1:
            raise ProcessingError("No %s study on date %s." % (modality, study_date))

    def _download_series(self, patient_id, study_uid, series_uids, pseudonym, study_folder):
        """Download all series to a specified folder for given series UIDs and pseudonymize
        the dataset before storing it to disk."""

        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid
        }
        for series_uid in series_uids:
            query_dict["SeriesInstanceUID"] = series_uid

            callback = partial(self._modify_dataset, pseudonym)
            results = self._get.send_c_get(query_dict, study_folder, callback)

            if not results or results[0]['status']['category'] != 'Success':
                msg = str(results)
                raise ProcessingError("Could not download series %s: %s" % (series_uid, msg))

    def _modify_dataset(self, pseudonym, ds):
        """Pseudonymize an incoming dataset with the given pseudonym and add the trial
        name to the DICOM header if specified."""

        if self._config.pseudonymize:
            self._anonymizer.anonymize_dataset(ds, patient_name=pseudonym)

        if self._config.trial_name:
            ds.ClinicalTrialProtocolID = self._config.trial_name

    def _create_archive(self, temp_folder, creation_time, archive_password):
        """Create a nearly empty archive with only an index file."""

        readme_path = os.path.join(temp_folder, "INDEX.txt")
        readme_file = open(readme_path, "w")
        readme_file.write(f"Archive created by {self._config.username} at {creation_time}.")
        readme_file.close()

        archive_path = os.path.join(self._config.archive_folder, self._config.archive_name)
        if Path(archive_path).is_file():
            raise ProcessingError(f"Archive ${archive_path} already exists.")

        self._add_to_archive(readme_path, archive_password)

    def _add_to_archive(self, path_to_add, archive_password):
        """Add a file or folder to an archive. If the archive does not exist 
        it will be created."""

        # TODO catch error like https://stackoverflow.com/a/46098513/166229
        password_option = '-p' + archive_password
        archive_path = os.path.join(self._config.archive_folder, self._config.archive_name + ".7z")
        cmd = ['7z', 'a', password_option, '-mhe=on', '-mx1', '-y', archive_path, path_to_add]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
        proc.wait()
        (_, stderr) = proc.communicate()
        if proc.returncode != 0:
            raise ProcessingError("Failed to add files to archive (%s)" % stderr)