import logging

from django.conf import settings
from django.template.defaultfilters import pluralize

from adit.core.errors import DicomError
from adit.core.models import DicomNode
from adit.core.types import DicomLogEntry
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator

from ..models import BatchQueryResult, BatchQueryTask

logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Executes a batch query task (one line in a batch query file) by utilizing the
    DICOM operator. Currently we don't make it abortable in between as it is fast enough.
    """

    def __init__(self, query_task: BatchQueryTask) -> None:
        self.query_task = query_task

        source = self.query_task.source
        assert source.node_type == DicomNode.NodeType.SERVER
        self.operator = DicomOperator(source.dicomserver)

    def start(self) -> tuple[BatchQueryTask.Status, str, list[DicomLogEntry]]:
        patient = self._fetch_patient()

        is_series_query = self.query_task.series_description or self.query_task.series_numbers

        if is_series_query:
            results = self._query_series(patient.PatientID)
            msg = f"{len(results)} series found"
        else:
            results = self._query_studies(patient.PatientID)
            msg = f"{len(results)} stud{pluralize(len(results), 'y,ies')} found"

        BatchQueryResult.objects.bulk_create(results)

        status: BatchQueryTask.Status = BatchQueryTask.Status.SUCCESS
        logs = self.operator.get_logs()
        for log in logs:
            if log["level"] == "Warning":
                status = BatchQueryTask.Status.WARNING

        self.operator.clear_logs()

        return (status, msg, logs)

    def _fetch_patient(self) -> ResultDataset:
        patient_id = self.query_task.patient_id
        patient_name = self.query_task.patient_name
        birth_date = self.query_task.patient_birth_date

        # PatientID has priority over PatientName and PatientBirthDate, but we check later
        # (see below) that the returned patient has the same PatientName and PatientBirthDate
        # if those were provided beside the PatientID
        if patient_id:
            patients = list(self.operator.find_patients(QueryDataset.create(PatientID=patient_id)))
        elif patient_name and birth_date:
            patients = list(
                self.operator.find_patients(
                    QueryDataset.create(PatientName=patient_name, PatientBirthDate=birth_date)
                )
            )
        else:
            raise DicomError("PatientName and PatientBirthDate are required.")

        if len(patients) == 0:
            raise DicomError("Patient not found.")

        if len(patients) > 1:
            raise DicomError("Multiple patients found.")

        patient = patients[0]

        # We can test for equality cause wildcards are not allowed during
        # batch query (only in selective transfer)
        if patient_id and patient_name and patient.PatientName != patient_name:
            raise DicomError("PatientName doesn't match found patient by PatientID.")

        if patient_id and birth_date and patient.PatientBirthDate != birth_date:
            raise DicomError("PatientBirthDate doesn't match found patient by PatientID.")

        return patient

    def _fetch_studies(self, patient_id: str) -> list[ResultDataset]:
        start_date = self.query_task.study_date_start
        end_date = self.query_task.study_date_end
        study_date = (start_date, end_date)

        modalities_query: list[str] = []
        if self.query_task.modalities:
            modalities_query = [
                modality
                for modality in self.query_task.modalities
                if modality not in settings.EXCLUDED_MODALITIES
            ]

        if not modalities_query:
            study_results = list(
                self.operator.find_studies(
                    QueryDataset.create(
                        PatientID=patient_id,
                        PatientName=self.query_task.patient_name,
                        PatientBirthDate=self.query_task.patient_birth_date,
                        AccessionNumber=self.query_task.accession_number,
                        StudyDate=study_date,
                        StudyDescription=self.query_task.study_description,
                    )
                )
            )
        else:
            seen: set[str] = set()
            study_results: list[ResultDataset] = []
            for modality in modalities_query:
                studies = list(
                    self.operator.find_studies(
                        QueryDataset.create(
                            PatientID=patient_id,
                            PatientName=self.query_task.patient_name,
                            PatientBirthDate=self.query_task.patient_birth_date,
                            AccessionNumber=self.query_task.accession_number,
                            StudyDate=study_date,
                            StudyDescription=self.query_task.study_description,
                            ModalitiesInStudy=modality,
                        )
                    )
                )
                for study in studies:
                    if study.StudyInstanceUID not in seen:
                        seen.add(study.StudyInstanceUID)
                        study_results.append(study)

        return sorted(study_results, key=lambda study: study.StudyDate)

    def _fetch_series(self, patient_id: str, study_uid: str) -> list[ResultDataset]:
        series_numbers = self.query_task.series_numbers

        if not series_numbers:
            series_query = QueryDataset.create(
                PatientID=patient_id,
                StudyInstanceUID=study_uid,
                SeriesDescription=self.query_task.series_description,
            )
            series_results = list(self.operator.find_series(series_query))
        else:
            seen: set[str] = set()
            series_results: list[ResultDataset] = []
            for series_number in series_numbers:
                series_query = QueryDataset.create(
                    PatientID=patient_id,
                    StudyInstanceUID=study_uid,
                    SeriesDescription=self.query_task.series_description,
                    SeriesNumber=series_number,
                )
                series_list = list(self.operator.find_series(series_query))
                for series in series_list:
                    if series.SeriesInstanceUID not in seen:
                        seen.add(series.SeriesInstanceUID)
                        series_results.append(series)

        return sorted(series_results, key=lambda series: int(series.get("SeriesNumber", 0)))

    def _query_studies(self, patient_id: str) -> list[BatchQueryResult]:
        studies = self._fetch_studies(patient_id)
        results: list[BatchQueryResult] = []
        for study in studies:
            batch_query_result = BatchQueryResult(
                job=self.query_task.job,
                query=self.query_task,
                patient_id=study.PatientID,
                patient_name=study.PatientName,
                patient_birth_date=study.PatientBirthDate,
                study_uid=study.StudyInstanceUID,
                accession_number=study.AccessionNumber,
                study_date=study.StudyDate,
                study_time=study.StudyTime,
                study_description=study.StudyDescription,
                modalities=study.ModalitiesInStudy,  # type: ignore TODO: pyright issue #6456
                image_count=study.NumberOfStudyRelatedInstances,
                pseudonym=self.query_task.pseudonym,
                series_uid="",
                series_description="",
                series_number="",
            )
            results.append(batch_query_result)

        return results

    def _query_series(self, patient_id: str) -> list[BatchQueryResult]:
        studies = self._fetch_studies(patient_id)

        results: list[BatchQueryResult] = []
        for study in studies:
            series_list = self._fetch_series(patient_id, study.StudyInstanceUID)
            for series in series_list:
                batch_query_result = BatchQueryResult(
                    job=self.query_task.job,
                    query=self.query_task,
                    patient_id=study.PatientID,
                    patient_name=study.PatientName,
                    patient_birth_date=study.PatientBirthDate,
                    study_uid=study.StudyInstanceUID,
                    accession_number=study.AccessionNumber,
                    study_date=study.StudyDate,
                    study_time=study.StudyTime,
                    study_description=study.StudyDescription,
                    modalities=[series.Modality],
                    image_count=study.NumberOfStudyRelatedInstances,
                    pseudonym=self.query_task.pseudonym,
                    series_uid=series.SeriesInstanceUID,
                    series_description=series.SeriesDescription,
                    series_number=str(series.SeriesNumber),
                )
                results.append(batch_query_result)

        return results
