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
    cleanup: bool = True
    patient_root_query_model_find: bool = True
    patient_root_query_model_get: bool = True
    
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

    def _get_download_folder(self):
        download_folder = self.config.destination_folder
        if not download_folder:
            download_folder = self.config.cache_folder
        return download_folder

    def _extract_pending_data(self, results):
        """Extract the data from a DicomOperation result."""

        filtered = filter(lambda x: x['status']['category'] == 'Pending', results)
        data = map(lambda x: x['data'], filtered)
        return data

    def _find_series_uids(self, patient_id, study_uid, modality=None):
        """Find all series UIDs for a given study UID.
        
        The series can be filtered by a modality (or multiple modalities).
        """
        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": "",
            "Modality": ""
        }
        results = self._find.send_c_find(query_dict)
        result_data = self._extract_pending_data(results)

        structured_reports = []
        series_uids = []
        for series in result_data:
            if series['Modality'] == 'SR':
                structured_reports.append(series['SeriesInstanceUID'])
            if series['Modality'] == modality:
                series_uids.append(series['SeriesInstanceUID'])

        if series_uids and self.config.include_structured_reports:
            series_uids += structured_reports

        return series_uids

    def download_study(self, patient_id, study_uid, folder_name=None, modality=None, pseudonym=None):
        pass

    def download_series(self, patient_id, study_uid, series_uid, folder_name=None, pseudonym=None):
        pass

    def upload_folder(self, folder):
        pass

    def move_to_destination_folder(self, folder_path):
        pass



