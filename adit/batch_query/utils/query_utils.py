import logging
from typing import Any, cast

from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore
from django.conf import settings
from django.template.defaultfilters import pluralize
from django.utils import timezone

from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.task_utils import hijack_logger, store_log_in_task

from ..models import BatchQueryResult, BatchQueryTask

logger = logging.getLogger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


def _create_source_connector(query_task: BatchQueryTask) -> DicomConnector:
    # An own function to easily mock the source connector in test_transfer_utils.py
    return DicomConnector(query_task.job.source.dicomserver)


class QueryExecutor:
    """
    Executes a batch query task (one line in a batch query file) by utilizing the
    DICOM connector.
    Currently we don't make it abortable in between as it is fast enough.
    """

    def __init__(self, query_task: BatchQueryTask, celery_task: AbortableCeleryTask) -> None:
        self.query_task = query_task
        self.celery_task = celery_task

        self.connector = _create_source_connector(query_task)

    def start(self) -> BatchQueryTask.Status:
        if self.query_task.status == BatchQueryTask.Status.CANCELED:
            return cast(BatchQueryTask.Status, self.query_task.status)

        self.query_task.status = BatchQueryTask.Status.IN_PROGRESS
        self.query_task.start = timezone.now()
        self.query_task.save()

        logger.info("Started %s.", self.query_task)

        handler, stream = hijack_logger(logger)

        try:
            patient = self._fetch_patient()

            all_results: list[list[dict[str, Any]]] = []  # a list of studies or series
            studies = self._query_studies(patient["PatientID"])
            is_series_query = self.query_task.series_description or self.query_task.series_numbers
            if studies:
                if is_series_query:
                    for study in studies:
                        series = self._query_series(study)
                        all_results.append(series)
                else:
                    all_results.append(studies)

            if len(all_results) == 0:
                self.query_task.status = BatchQueryTask.Status.WARNING
                self.query_task.message = "No studies / series found"
            else:
                flattened_results = [
                    study_or_series
                    for studies_or_series in all_results
                    for study_or_series in studies_or_series
                ]

                saved_results = self._save_results(flattened_results)

                self.query_task.status = BatchQueryTask.Status.SUCCESS
                num = len(saved_results)
                if is_series_query:
                    message = f"{num} series"
                else:
                    message = f"{num} stud{pluralize(num, 'y,ies')}"
                self.query_task.message = f"{message} found"
        except Exception as err:
            logger.exception("Error during %s", self.query_task)
            self.query_task.status = BatchQueryTask.Status.FAILURE
            self.query_task.message = str(err)
        finally:
            store_log_in_task(logger, handler, stream, self.query_task)
            self.query_task.end = timezone.now()
            self.query_task.save()

        return self.query_task.status

    def _fetch_patient(self) -> dict[str, Any]:
        patient_id = self.query_task.patient_id
        patient_name = self.query_task.patient_name
        birth_date = self.query_task.patient_birth_date

        # PatientID has priority over PatientName and PatientBirthDate, but we check later
        # (see below) that the returned patient has the same PatientName and PatientBirthDate
        # if those were provided beside the PatientID
        if patient_id:
            patients = self.connector.find_patients(
                {
                    "PatientID": patient_id,
                    "PatientName": "",
                    "PatientBirthDate": "",
                }
            )
        else:
            assert patient_name
            assert birth_date
            patients = self.connector.find_patients(
                {
                    "PatientID": "",
                    "PatientName": patient_name,
                    "PatientBirthDate": birth_date,
                }
            )

        if len(patients) == 0:
            raise ValueError("Patient not found.")

        if len(patients) > 1:
            raise ValueError("Multiple patients found.")

        patient = patients[0]

        # We can test for equality cause wildcards are not allowed during
        # batch query (only in selective transfer)
        if patient_id and patient_name and patient["PatientName"] != patient_name:
            raise ValueError("PatientName doesn't match found patient by PatientID.")

        if patient_id and birth_date and patient["PatientBirthDate"] != birth_date:
            raise ValueError("PatientBirthDate doesn't match found patient by PatientID.")

        return patient

    def _query_studies(self, patient_id: str) -> list[dict[str, Any]]:
        study_date = ""
        if self.query_task.study_date_start:
            if not self.query_task.study_date_end:
                study_date = self.query_task.study_date_start.strftime(DICOM_DATE_FORMAT) + "-"
            elif self.query_task.study_date_start == self.query_task.study_date_end:
                study_date = self.query_task.study_date_start.strftime(DICOM_DATE_FORMAT)
            else:
                study_date = (
                    self.query_task.study_date_start.strftime(DICOM_DATE_FORMAT)
                    + "-"
                    + self.query_task.study_date_end.strftime(DICOM_DATE_FORMAT)
                )
        elif self.query_task.study_date_end:
            study_date = "-" + self.query_task.study_date_end.strftime(DICOM_DATE_FORMAT)

        modalities_to_query: list[str] = []
        if self.query_task.modalities_list:
            modalities_to_query = [
                modality
                for modality in self.query_task.modalities_list
                if modality not in settings.EXCLUDED_MODALITIES
            ]

        studies = self.connector.find_studies(
            {
                "PatientID": patient_id,
                "PatientName": self.query_task.patient_name,
                "PatientBirthDate": self.query_task.patient_birth_date,
                "StudyInstanceUID": "",
                "AccessionNumber": self.query_task.accession_number,
                "StudyDate": study_date,
                "StudyTime": "",
                "StudyDescription": self.query_task.study_description,
                "ModalitiesInStudy": modalities_to_query,
                "NumberOfStudyRelatedInstances": "",
            }
        )

        return studies

    def _query_series(self, study: dict[str, Any]) -> list[dict[str, Any]]:
        found_series = self.connector.find_series(
            {
                "PatientID": study["PatientID"],
                "StudyInstanceUID": study["StudyInstanceUID"],
                "SeriesInstanceUID": "",
                "SeriesDescription": self.query_task.series_description,
                "SeriesNumber": self.query_task.series_numbers_list,
            }
        )

        for series in found_series:
            series.update(study)

        return found_series

    def _save_results(self, results: list[dict[str, Any]]) -> list[BatchQueryResult]:
        results_to_save = []
        for result in results:
            series_uid = ""
            if "SeriesInstanceUID" in result:
                series_uid = result["SeriesInstanceUID"]

            study_description = ""
            if "StudyDescription" in result:
                study_description = result["StudyDescription"]

            series_description = ""
            if "SeriesDescription" in result:
                series_description = result["SeriesDescription"]

            series_number = ""
            if "SeriesNumber" in result:
                series_number = result["SeriesNumber"]

            result_to_save = BatchQueryResult(
                job=self.query_task.job,
                query=self.query_task,
                patient_id=result["PatientID"],
                patient_name=result["PatientName"],
                patient_birth_date=result["PatientBirthDate"],
                study_uid=result["StudyInstanceUID"],
                accession_number=result["AccessionNumber"],
                study_date=result["StudyDate"],
                study_time=result["StudyTime"],
                study_description=study_description,
                modalities=result["ModalitiesInStudy"],
                image_count=result["NumberOfStudyRelatedInstances"],
                pseudonym=self.query_task.pseudonym,
                series_uid=series_uid,
                series_description=series_description,
                series_number=series_number,
            )

            results_to_save.append(result_to_save)

        BatchQueryResult.objects.bulk_create(results_to_save)

        return results_to_save
