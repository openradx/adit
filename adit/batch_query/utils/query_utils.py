import logging
from typing import Iterable

from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore
from django.conf import settings
from django.template.defaultfilters import pluralize
from pydicom import Dataset

from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import create_query_dataset

from ..models import BatchQueryResult, BatchQueryTask

logger = logging.getLogger(__name__)


def _create_source_operator(query_task: BatchQueryTask) -> DicomOperator:
    # An own function to easily mock the source connector in test_transfer_utils.py
    return DicomOperator(query_task.job.source.dicomserver)


class QueryExecutor:
    """
    Executes a batch query task (one line in a batch query file) by utilizing the
    DICOM operator. Currently we don't make it abortable in between as it is fast enough.
    """

    def __init__(self, query_task: BatchQueryTask, celery_task: AbortableCeleryTask) -> None:
        self.query_task = query_task
        self.celery_task = celery_task

        self.operator = _create_source_operator(query_task)

    def start(self) -> tuple[BatchQueryTask.Status, str]:
        patient = self._fetch_patient()

        is_series_query = self.query_task.series_description or self.query_task.series_numbers

        if is_series_query:
            results = self._query_series(patient.PatientID)
            msg = f"{len(results)} series found"
        else:
            results = self._query_studies(patient.PatientID)
            msg = f"{len(results)} stud{pluralize(len(results), 'y,ies')} found"

        BatchQueryResult.objects.bulk_create(results)

        return (BatchQueryTask.Status.SUCCESS, msg)

    def _fetch_patient(self) -> Dataset:
        patient_id = self.query_task.patient_id
        patient_name = self.query_task.patient_name
        birth_date = self.query_task.patient_birth_date

        # PatientID has priority over PatientName and PatientBirthDate, but we check later
        # (see below) that the returned patient has the same PatientName and PatientBirthDate
        # if those were provided beside the PatientID
        if patient_id:
            patients = list(self.operator.find_patients(create_query_dataset(PatientID=patient_id)))
        elif patient_name and birth_date:
            patients = list(
                self.operator.find_patients(
                    create_query_dataset(PatientName=patient_name, PatientBirthDate=birth_date)
                )
            )
        else:
            raise ValueError("PatientName and PatientBirthDate are required.")

        if len(patients) == 0:
            raise ValueError("Patient not found.")

        if len(patients) > 1:
            raise ValueError("Multiple patients found.")

        patient = patients[0]

        # We can test for equality cause wildcards are not allowed during
        # batch query (only in selective transfer)
        if patient_id and patient_name and patient.PatientName != patient_name:
            raise ValueError("PatientName doesn't match found patient by PatientID.")

        if patient_id and birth_date and patient.PatientBirthDate != birth_date:
            raise ValueError("PatientBirthDate doesn't match found patient by PatientID.")

        return patient

    def _fetch_studies(self, patient_id: str) -> list[Dataset]:
        start_date = self.query_task.study_date_start
        end_date = self.query_task.study_date_end
        study_date = (start_date, end_date)

        modalities_query: list[str] = []
        if self.query_task.modalities_list:
            modalities_query = [
                modality
                for modality in self.query_task.modalities_list
                if modality not in settings.EXCLUDED_MODALITIES
            ]

        study_query = create_query_dataset(
            PatientID=patient_id,
            PatientName=self.query_task.patient_name,
            PatientBirthDate=self.query_task.patient_birth_date,
            AccessionNumber=self.query_task.accession_number,
            StudyDate=study_date,
            StudyDescription=self.query_task.study_description,
        )

        if not modalities_query:
            study_results = list(self.operator.find_studies(study_query))
        else:
            seen: set[str] = set()
            study_results: list[Dataset] = []
            for modality in modalities_query:
                study_query.ModalitiesInStudy = modality
                studies = self.operator.find_studies(study_query)
                for study in studies:
                    if study.StudyInstanceUID not in seen:
                        seen.add(study.StudyInstanceUID)
                        study_results.append(study)

        return sorted(study_results, key=lambda study: study.StudyDate)

    def _fetch_series(self, patient_id: str, study_uid: str) -> list[Dataset]:
        series_numbers = self.query_task.series_numbers_list

        series_query = create_query_dataset(
            PatientID=patient_id,
            StudyInstanceUID=study_uid,
            SeriesDescription=self.query_task.series_description,
        )

        if not series_numbers:
            series_results = list(self.operator.find_series(series_query))
        else:
            seen: set[str] = set()
            series_results: list[Dataset] = []
            for series_number in series_numbers:
                series_query.SeriesNumber = series_number
                series_list = self.operator.find_series(series_query)
                for series in series_list:
                    if series.SeriesInstanceUID not in seen:
                        seen.add(series.SeriesInstanceUID)
                        series_results.append(series)

        return sorted(series_results, key=lambda series: int(series.get("SeriesNumber", 0)))

    def _query_studies(self, patient_id: str) -> list[BatchQueryResult]:
        studies = self._fetch_studies(patient_id)
        results: list[BatchQueryResult] = []
        for study in studies:
            modalities = study.get("ModalitiesInStudy", "")
            if isinstance(modalities, Iterable):
                modalities = ", ".join(modalities)

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
                # Modalities of all series in this study
                modalities=modalities,
                # Optional in the DICOM standard
                image_count=study.get("NumberOfStudyRelatedInstances"),
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
                    # Modality only of this series
                    modalities=series.Modality,
                    # Optional in the DICOM standard
                    image_count=study.get("NumberOfStudyRelatedInstances", None),
                    pseudonym=self.query_task.pseudonym,
                    series_uid=series.SeriesInstanceUID,
                    series_description=series.SeriesDescription,
                    series_number=str(series.get("SeriesNumber", "")),
                )
                results.append(batch_query_result)

        return results
