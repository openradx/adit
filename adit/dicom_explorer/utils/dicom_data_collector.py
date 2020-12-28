from typing import Dict, Any
from datetime import datetime
from adit.core.utils.dicom_connector import DicomConnector


class DicomDataCollector:
    def __init__(self, connector: DicomConnector):
        self.connector = connector

    def _fetch_patient(self, patient_id: str) -> Dict[str, Any]:
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.html#table_C.6-1

        if not patient_id:
            raise AssertionError("Missing Patient ID.")

        patients = self.connector.find_patients(
            {
                "PatientID": patient_id,
                "PatientName": "",
                "PatientBirthDate": "",
                "PatientSex": "",
                "NumberOfPatientRelatedStudies": "",
            }
        )

        if len(patients) > 1:
            raise ValueError(f"Multiple patients found for Patient ID {patient_id}.")

        if not patients:
            return None

        return patients[0]

    def _fetch_studies(self, patient_id="", accession_number="", study_uid=""):
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.html#table_C.6-2
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.2.html#table_C.6-5

        if not (patient_id or accession_number or study_uid):
            raise AssertionError(
                "Missing Patient ID, Accession Number or Study Instance UID."
            )

        studies = self.connector.find_studies(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "AccessionNumber": accession_number,
                "StudyDescription": "",
                "StudyDate": "",
                "StudyTime": "",
                "ModalitiesInStudy": "",
                "NumberOfStudyRelatedSeries": "",
                "NumberOfStudyRelatedInstances": "",
            }
        )

        studies = sorted(
            studies,
            key=lambda study: datetime.combine(study["StudyDate"], study["StudyTime"]),
            reverse=True,
        )

        return studies

    def _fetch_study(self, patient_id="", accession_number="", study_uid=""):
        if not (accession_number or study_uid):
            raise AssertionError("Missing Accession Number or Study Instance UID.")

        studies = self._fetch_studies(patient_id, accession_number, study_uid)

        if len(studies) > 1:
            if accession_number:
                raise ValueError(
                    f"Multiple studies found for an Accession Number {accession_number}"
                )

            if study_uid:
                raise ValueError(
                    f"Multiple studies found for a Study Instance UID {study_uid}"
                )

        if not studies:
            return None

        return studies[0]

    def _fetch_series_list(self, patient_id="", study_uid="", series_uid=""):
        # http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_C.6.html#table_C.6-3

        if not study_uid:
            raise AssertionError("Missing Study Instance UID.")

        series_list = self.connector.find_series(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "SeriesInstanceUID": series_uid,
                "SeriesNumber": "",
                "SeriesDescription": "",
                "Modality": "",
                "NumberOfSeriesRelatedInstances": "",
            }
        )

        series_list = sorted(
            series_list,
            key=lambda x: float("inf")
            if x["SeriesNumber"] is None
            else x["SeriesNumber"],
        )

        return series_list

    def _fetch_series(self, patient_id="", study_uid="", series_uid=""):
        if not series_uid:
            raise AssertionError("Missing Series Instance UID.")

        series_list = self._fetch_series_list(patient_id, study_uid, series_uid)

        if len(series_list) > 1:
            raise ValueError(
                f"Multiple series found for Series Instance UID {series_uid}"
            )

        if not series_list:
            return None

        return series_list[0]

    def collect_patient_data(self, patient_id, with_studies=True):
        patient = self._fetch_patient(patient_id)
        studies = None
        if patient and with_studies:
            studies = self._fetch_studies(patient["PatientID"])
        return patient, studies

    def collect_study_data(
        self, patient_id, accession_number, study_uid, with_series=True
    ):
        if patient_id:
            patient, _ = self.collect_patient_data(patient_id, with_studies=False)
            study = self._fetch_study(patient_id, accession_number, study_uid)
        else:
            study = self._fetch_studies(
                accession_number=accession_number, study_uid=study_uid
            )
            patient = None
            if study:
                patient, _ = self.collect_patient_data(
                    study["PatientID"], with_studies=False
                )

        series_list = None
        if study and with_series:
            series_list = self._fetch_series_list(
                study["PatientID"], study["StudyInstanceUID"]
            )

        return patient, study, series_list

    def collect_series_data(self, patient_id, accession_number, study_uid, series_uid):
        patient, study, _ = self.collect_study_data(
            patient_id, accession_number, study_uid, with_series=False
        )
        series = None
        if study:
            series = self._fetch_series(
                study["PatientID"], study["StudyInstanceUID"], series_uid
            )

        return patient, study, series
