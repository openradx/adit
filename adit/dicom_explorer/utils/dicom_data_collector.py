from datetime import datetime

from django.conf import settings
from pydicom import Dataset

from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator


class DicomDataCollector:
    def __init__(self, server: DicomServer):
        timeout = settings.DICOM_EXPLORER_RESPONSE_TIMEOUT
        self.operator = DicomOperator(server, connection_retries=1, timeout=timeout)

    def collect_patients(
        self,
        query: Dataset,
        limit_results: int | None = None,
    ):
        patients = self.operator.find_patients(query, limit_results=limit_results)
        return sorted(patients, key=lambda patient: patient.PatientName)

    def collect_studies(self, query: Dataset, limit_results: int | None = None):
        studies = self.operator.find_studies(query, limit_results=limit_results)

        return sorted(
            studies,
            key=lambda study: datetime.combine(study.StudyDate, study.StudyTime),
            reverse=True,
        )

    def collect_series(self, query: Dataset):
        if "StudyInstanceUID" not in query:
            raise AssertionError("Missing Study Instance UID for querying series.")

        series_list = self.operator.find_series(query)

        return sorted(
            series_list,
            key=lambda series: float("inf") if series.SeriesNumber is None else series.SeriesNumber,
        )
