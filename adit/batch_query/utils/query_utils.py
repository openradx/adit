import logging
from typing import Any, Dict, List, Optional
from django.conf import settings
from django.template.defaultfilters import pluralize
from django.utils import timezone
from celery.contrib.abortable import AbortableTask as AbortableCeleryTask
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

    def __init__(
        self, query_task: BatchQueryTask, celery_task: AbortableCeleryTask
    ) -> None:
        self.query_task = query_task
        self.celery_task = celery_task

        self.connector = _create_source_connector(query_task)

    # pylint: disable=too-many-branches
    def start(self) -> BatchQueryTask.Status:
        if self.query_task.status == BatchQueryTask.Status.CANCELED:
            return self.query_task.status

        self.query_task.status = BatchQueryTask.Status.IN_PROGRESS
        self.query_task.start = timezone.now()
        self.query_task.save()

        logger.info("Started %s.", self.query_task)

        handler, stream = hijack_logger(logger)

        # pylint: disable=too-many-nested-blocks
        try:
            patients = self._fetch_patients()

            if len(patients) == 0:
                self.query_task.status = BatchQueryTask.Status.FAILURE
                self.query_task.message = "Patient not found."
            else:
                all_studies = []  # a list of study lists (per patient)
                for patient in patients:
                    studies = self._query_studies(patient["PatientID"])
                    if studies:
                        if (
                            self.query_task.series_description
                            or self.query_task.series_number
                        ):
                            for study in studies:
                                series = self._query_series(study)
                                all_studies.append(series)
                        else:
                            all_studies.append(studies)

                if len(all_studies) == 0:
                    self.query_task.status = BatchQueryTask.Status.WARNING
                    self.query_task.message = "No studies for patient found."
                else:
                    all_studies_flattened = [
                        study for studies in all_studies for study in studies
                    ]
                    results = self._save_results(all_studies_flattened)

                    num = len(results)
                    if self.query_task.series_description:
                        study_count = f"{num} series"
                    else:
                        study_count = f"{num} stud{pluralize(num, 'y,ies')}"

                    if len(all_studies) == 1:  # Only studies of one patient found
                        self.query_task.status = BatchQueryTask.Status.SUCCESS
                        self.query_task.message = f"{study_count} found."
                    else:  # Studies of multiple patients found
                        # We still allow multiple patient IDs as the same patient
                        # may have different Patient IDs if the studies were imported
                        # from external.
                        self.query_task.status = BatchQueryTask.Status.WARNING
                        self.query_task.message = (
                            f"Multiple patients found with overall {study_count}."
                        )
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Error during %s", self.query_task)
            self.query_task.status = BatchQueryTask.Status.FAILURE
            self.query_task.message = str(err)
        finally:
            store_log_in_task(logger, handler, stream, self.query_task)
            self.query_task.end = timezone.now()
            self.query_task.save()

        return self.query_task.status

    def _fetch_patients(self) -> Optional[Dict[str, Any]]:
        return self.connector.find_patients(
            {
                "PatientID": self.query_task.patient_id,
                "PatientName": self.query_task.patient_name,
                "PatientBirthDate": self.query_task.patient_birth_date,
            }
        )

    def _query_studies(self, patient_id: str) -> List[Dict[str, Any]]:
        study_date = ""
        if self.query_task.study_date_start:
            if not self.query_task.study_date_end:
                study_date = (
                    self.query_task.study_date_start.strftime(DICOM_DATE_FORMAT) + "-"
                )
            elif self.query_task.study_date_start == self.query_task.study_date_end:
                study_date = self.query_task.study_date_start.strftime(
                    DICOM_DATE_FORMAT
                )
            else:
                study_date = (
                    self.query_task.study_date_start.strftime(DICOM_DATE_FORMAT)
                    + "-"
                    + self.query_task.study_date_end.strftime(DICOM_DATE_FORMAT)
                )
        elif self.query_task.study_date_end:
            study_date = "-" + self.query_task.study_date_end.strftime(
                DICOM_DATE_FORMAT
            )

        modalities = []
        if self.query_task.modalities:
            modalities = [
                modality
                for modality in self.query_task.modalities
                if modality not in settings.EXCLUDE_MODALITIES
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
                "StudyDescription": "",
                "ModalitiesInStudy": modalities,
                "NumberOfStudyRelatedInstances": "",
            }
        )

        return studies

    def _query_series(self, study: Dict[str, Any]) -> List[Dict[str, Any]]:
        found_series = self.connector.find_series(
            {
                "PatientID": study["PatientID"],
                "StudyInstanceUID": study["StudyInstanceUID"],
                "SeriesInstanceUID": "",
                "SeriesDescription": self.query_task.series_description,
                "SeriesNumber": self.query_task.series_number,
            }
        )

        for series in found_series:
            series.update(study)

        return found_series

    def _save_results(self, studies: List[Dict[str, Any]]) -> List[BatchQueryResult]:
        results = []
        for study in studies:
            series_uid = ""
            if "SeriesInstanceUID" in study:
                series_uid = study["SeriesInstanceUID"]
            series_description = ""
            if "SeriesDescription" in study:
                series_description = study["SeriesDescription"]
            series_number = ""
            if "SeriesNumber" in study:
                series_number = study["SeriesNumber"]
            result = BatchQueryResult(
                job=self.query_task.job,
                query=self.query_task,
                patient_id=study["PatientID"],
                patient_name=study["PatientName"],
                patient_birth_date=study["PatientBirthDate"],
                study_uid=study["StudyInstanceUID"],
                accession_number=study["AccessionNumber"],
                study_date=study["StudyDate"],
                study_time=study["StudyTime"],
                study_description=study["StudyDescription"],
                modalities=study["ModalitiesInStudy"],
                image_count=study["NumberOfStudyRelatedInstances"],
                pseudonym=self.query_task.pseudonym,
                series_uid=series_uid,
                series_description=series_description,
                series_number=series_number,
            )
            results.append(result)

        BatchQueryResult.objects.bulk_create(results)

        return results
