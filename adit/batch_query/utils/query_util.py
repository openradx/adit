import logging
import re
from django.utils import timezone
from adit.core.utils.dicom_connector import DicomConnector
from ..models import BatchQueryTask, BatchQueryResult

logger = logging.getLogger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


class QueryUtil:
    def __init__(self, query_task: BatchQueryTask) -> None:
        self.query_task = query_task

    def start_query(self):
        query_task = self.query_task

        if query_task.status == BatchQueryTask.Status.CANCELED:
            return query_task.status

        query_task.status = BatchQueryTask.Status.IN_PROGRESS
        query_task.start = timezone.now()
        query_task.save()

        try:
            studies = self._query_studies()
            results = self._save_results(studies)

            if results:
                query_task.status = BatchQueryTask.Status.SUCCESS
                query_task.message = f"Found {len(results)} studies."
            else:
                query_task.status = BatchQueryTask.Status.WARNING
                query_task.message = "No studies found."
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Error during %s", query_task)
            query_task.status = BatchQueryTask.Status.FAILURE
            query_task.message = str(err)
        finally:
            query_task.end = timezone.now()
            query_task.save()

        return query_task.status

    def _query_studies(self):
        query_task = self.query_task

        patient_name = re.sub(r"\s*,\s*", "^", self.query_task.patient_name)

        study_date = ""
        if query_task.study_date_start:
            if not query_task.study_date_end:
                study_date = (
                    query_task.study_date_start.strptime(DICOM_DATE_FORMAT) + "-"
                )
            elif query_task.study_date_start == query_task.study_date_end:
                study_date = query_task.study_date_start.strptime(DICOM_DATE_FORMAT)
            else:
                study_date = (
                    query_task.study_date_start.strptime(DICOM_DATE_FORMAT)
                    + "-"
                    + query_task.study_date_end.strptime(DICOM_DATE_FORMAT)
                )
        elif query_task.study_date_end:
            study_date = "-" + query_task.study_date_end.strptime(DICOM_DATE_FORMAT)

        connector: DicomConnector = query_task.job.source.dicomserver.create_connector()

        studies = connector.find_studies(
            {
                "PatientID": query_task.patient_id,
                "PatientName": patient_name,
                "PatientBirthDate": query_task.patient_birth_date,
                "StudyInstanceUID": "",
                "AccessionNumber": query_task.accession_number,
                "StudyDate": study_date,
                "StudyTime": "",
                "StudyDescription": "",
                "ModalitiesInStudy": query_task.modalities,
                "NumberOfStudyRelatedInstances": "",
            }
        )

        return studies

    def _save_results(self, studies):
        query_task = self.query_task
        query_job = self.query_task.job

        results = []
        for study in studies:
            result = BatchQueryResult(
                job=query_job,
                query=query_task,
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
            )
            results.append(result)

        BatchQueryResult.objects.bulk_create(results)

        return results
