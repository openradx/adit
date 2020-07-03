from .anonymizer import Anonymizer
from .dicom_operations import (
    DicomFind, DicomGet, DicomStore,
    DicomOperation, DicomOperationConfig
)

@dataclass
class DicomTransferrerConfig:
    username: str
    client_ae_title: str
    cache_folder: str
    source_ae_title: str
    source_ip: str
    source_port: int
    destination_ae_title: str = None
    destination_ip: str = None
    destination_port: int = None
    destination_folder: str = None
    patient_root_query_model_find: bool = True
    patient_root_query_model_get: bool = True
    download_series_in_own_folder = True
    cleanup: bool = True


class TransferError(Exception):
    pass

    
class DicomTransferrer:
    def __init__(self, config: DicomTransferrerConfig):
        self.config = config

        self._anonymizer = Anonymizer()

        self._find = DicomFind(DicomOperationConfig(
            self.config.client_ae_title,
            self.config.source_ae_title,
            self.config.source_ip,
            self.config.source_port,
            self.config.patient_root_query_model_find
        ))
        self._get = DicomGet(DicomOperationConfig(
            self.config.client_ae_title,
            self.config.source_ae_title,
            self.config.source_ip,
            self.config.source_port,
            self.config.patient_root_query_model_get
        ))
        self._store = DicomStore(DicomOperationConfig(
            self.config.client_ae_title,
            self.config.destination_ae_title,
            self.config.destination_ip,
            self.config.destination_port
        ))

    def get_download_folder(self):
        download_folder = self.config.destination_folder
        if not download_folder:
            download_folder = self.config.cache_folder
        return download_folder

    def _extract_pending_data(self, results):
        """Extract the data from a DicomOperation result."""

        filtered = filter(lambda x: x['status']['category'] == 'Pending', results)
        data = map(lambda x: x['data'], filtered)
        return data

    def fetch_study_modalities(self, patient_id, study_uid):
        series_list = self.find_series(patient_id, study_uid)
        ...

    def find_patients(self, patient_id, patient_name, patient_birth_date):
        """Find patients with the given patient ID and/or patient name and birth date."""

        query_dict = {
            'QueryRetrieveLevel': 'PATIENT',
            'PatientID': patient_id,
            'PatientName': patient_name,
            'PatientBirthDate': patient_birth_date
        }
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

        patient_list = []
        for item in result_data:
            patient_list.append({
                'PatientID': item['PatientID'],
                'PatientName': item['PatientName'],
                'PatientBirthDate': item['PatientBirthDate']
            })

        return patient_list

    def find_studies(self, patient_id, study_date='', modality=None):
        """Find all studies for a given patient and filter optionally by
        study date and/or modality."""

        query_dict = {
            'QueryRetrieveLevel': 'STUDY',
            'PatientID': patient_id,
            'StudyDate': study_date,
            'StudyInstanceUID': '',
            'StudyDescription': ''
        }
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

        study_list = []
        for item in result_data:
            pass

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
            "Modality": ""
        }
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

        series_list = []
        for item in result_data:
            if (modality is None 
                    or item['Modality'] == modality
                    or item['Modality'] in modality):

                series_list.append({
                    'SeriesInstanceUID': item['SeriesInstanceUID'],
                    'SeriesDescription': item['SeriesDescription'],
                    'Modality': item['Modality']
                })

        return series_list

    def download_patient(self, patient_id, folder_path, modality=None, callback=None):
        pass

    def download_study(self, patient_id, study_uid, folder_path=None, modality=None, callback=None):
        series_list = self.find_series(patient_id, study_uid, modality)
        for series in series_list:

            self.download_series(patient_id, study_uid, series_uid, callback)

    def download_series(self, patient_id, study_uid, series_uid, folder_path=None, callback=None):
        """Download all series to a specified folder for given series UIDs and pseudonymize
        the dataset before storing it to disk."""

        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid
        }

        results = self._get.send_c_get(query_dict, folder_path, callback)

        if not results or results[0]['status']['category'] != 'Success':
            msg = str(results)
            raise TransferError("Could not download series %s: %s" % (series_uid, msg))

    def upload_folder(self, folder):
        pass
