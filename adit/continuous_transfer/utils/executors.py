from datetime import date, timedelta

from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore

from adit.continuous_transfer.models import ContinuousQueryTask, ContinuousTransferJob
from adit.core.utils.dicom_connector import DicomConnector


def _create_source_connector(query_task: ContinuousQueryTask) -> DicomConnector:
    # An own function to easily mock the source connector in tests
    return DicomConnector(query_task.job.source.dicomserver)


class QueryExecutor:
    def __init__(self, query_task: ContinuousQueryTask, celery_task: AbortableCeleryTask):
        self.query_task = query_task
        self.celery_task = celery_task

        self.connector = _create_source_connector(query_task)

    def _query_studies(self):
        study_date: date
        last_processed = self.query_task.job.last_processed
        if last_processed:
            study_date = last_processed + timedelta(days=1)
        else:
            study_date = self.query_task.job.study_date_start

        while True:
            studies = self.connector.find_studies(
                {
                    "StudyDate": study_date,
                    "PatientID": self.query_task.job.patient_id,
                    "PatientName": self.query_task.job.patient_name,
                    "PatientBirthDate": self.query_task.job.patient_birth_date,
                    "ModalitiesInStudy": self.query_task.job.modalities,
                    "StudyDescription": self.query_task.job.study_description,
                    "SeriesDescription": self.query_task.job.series_description,
                    "SeriesNumber": self.query_task.job.series_numbers,
                }
            )

            if studies:
                break

            study_date += timedelta(days=1)

            study_date_end = self.query_task.job.study_date_end
            if study_date_end and study_date > study_date_end:
                break

            # limit how many days we query in one go

        if not studies:
            # process query task in e.g. 24 hours
            pass

        # make up transfer tasks with found studies


class TransferExecutor:
    pass
