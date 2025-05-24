from django.conf import settings

from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator


class DicomDataCollector:
    def __init__(self, server: DicomServer):
        timeout = settings.DICOM_EXPLORER_RESPONSE_TIMEOUT
        self.operator = DicomOperator(server, connection_retries=1, dimse_timeout=timeout)

    def collect_patients(
        self,
        query: QueryDataset,
        limit_results: int | None = None,
    ) -> list[ResultDataset]:
        patients = list(self.operator.find_patients(query, limit_results=limit_results))
        return sorted(patients, key=lambda patient: patient.PatientName)

    def collect_studies(self, query: QueryDataset, limit_results: int | None = None):
        studies = list(self.operator.find_studies(query, limit_results=limit_results))

        return sorted(studies, key=lambda study: study.StudyDateTime, reverse=True)

    def collect_series(self, query: QueryDataset) -> list[ResultDataset]:
        if not query.has("StudyInstanceUID"):
            raise AssertionError("Missing Study Instance UID for querying series.")

        series_list = list(self.operator.find_series(query))

        return sorted(
            series_list,
            key=lambda series: float("inf") if series.SeriesNumber is None else series.SeriesNumber,
        )
