from datetime import datetime
from django.conf import settings
from adit.core.models import DicomServer
from adit.core.utils.dicom_connector import DicomConnector


class DicomDataCollector:
    def __init__(self, server: DicomServer):
        timeout = settings.DICOM_EXPLORER_RESPONSE_TIMEOUT
        self.connector = DicomConnector(
            server,
            DicomConnector.Config(
                connection_retries=1,
                acse_timeout=timeout,
                dimse_timeout=timeout,
                network_timeout=timeout,
            ),
        )

    def collect_patient_data(self, patient_id=None, query=None, limit_results=None):
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.html#table_C.6-1

        if query is None:
            query = {}

        query = {
            "PatientID": "",
            "PatientName": "",
            "PatientBirthDate": "",
            "PatientSex": "",
            "NumberOfPatientRelatedStudies": "",
        } | query  # python 3.9 merge dicts

        if patient_id is not None:
            query["PatientID"] = patient_id

        patients = self.connector.find_patients(query, limit_results=limit_results)

        patients = sorted(patients, key=lambda patient: patient["PatientName"])

        return patients

    def collect_study_data(self, study_uid=None, query=None, limit_results=None):
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.html#table_C.6-2
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.2.html#table_C.6-5

        if query is None:
            query = {}

        query = {
            "PatientID": "",
            "StudyInstanceUID": "",
            "AccessionNumber": "",
            "StudyDescription": "",
            "StudyDate": "",
            "StudyTime": "",
            "ModalitiesInStudy": "",
            "NumberOfStudyRelatedSeries": "",
            "NumberOfStudyRelatedInstances": "",
        } | query  # python 3.9 merge dicts

        if study_uid is not None:
            query["StudyInstanceUID"] = study_uid

        studies = self.connector.find_studies(query, limit_results=limit_results)

        studies = sorted(
            studies,
            key=lambda study: datetime.combine(study["StudyDate"], study["StudyTime"]),
            reverse=True,
        )

        return studies

    def collect_series_data(self, study_uid, series_uid=None, query=None):
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.html#table_C.6-3

        if not study_uid:
            raise AssertionError("Missing Study Instance UID for quering series.")

        if query is None:
            query = {}

        query = {
            "PatientID": "",
            "StudyInstanceUID": "",
            "SeriesInstanceUID": "",
            "SeriesNumber": "",
            "SeriesDescription": "",
            "Modality": "",
            "NumberOfSeriesRelatedInstances": "",
        } | query  # python 3.9 merge dicts

        query["StudyInstanceUID"] = study_uid

        if series_uid is not None:
            query["SeriesInstanceUID"] = series_uid

        series_list = self.connector.find_series(query)

        if series_uid and len(series_list) == 0:
            raise ValueError(
                f"No series found for Study Instance UID {study_uid} "
                f"and Series Instance UID {series_uid}."
            )

        if series_uid and len(series_list) > 1:
            raise ValueError(f"Multiple series found for Series Instance UID {series_uid}")

        series_list = sorted(
            series_list,
            key=lambda x: float("inf") if x["SeriesNumber"] is None else x["SeriesNumber"],
        )

        return series_list
