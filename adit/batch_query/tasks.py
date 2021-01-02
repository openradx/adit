import re
from typing import List
from celery import shared_task, chord
from celery import Task as CeleryTask
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.mail import send_job_finished_mail
from adit.core.utils.task_utils import (
    prepare_dicom_job,
    prepare_dicom_task,
    finish_dicom_job,
    handle_job_failure,
)
from .models import (
    BatchQueryJob,
    BatchQueryTask,
    BatchQueryResult,
    BatchQuerySettings,
)

logger = get_task_logger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


@shared_task(ignore_result=True)
def batch_query(query_job_id: int):
    query_job = BatchQueryJob.objects.get(id=query_job_id)
    prepare_dicom_job(query_job)

    priority = settings.BATCH_QUERY_DEFAULT_PRIORITY
    if query_job.urgent:
        priority = settings.BATCH_QUERY_URGENT_PRIORITY

    process_queries = [
        process_query.s(query.id).set(priority=priority)
        for query in query_job.queries.all()
    ]

    chord(process_queries)(
        on_job_finished.s(query_job.id).on_error(on_job_failed.s(job_id=query_job.id))
    )


@shared_task(bind=True)
def process_query(self: CeleryTask, query_task_id: BatchQueryTask):
    query_task = BatchQueryTask.objects.get(id=query_task_id)
    prepare_dicom_task(query_task, BatchQuerySettings.get(), self)

    if query_task.status == BatchQueryTask.Status.CANCELED:
        return query_task.status

    query_task.status = BatchQueryTask.Status.IN_PROGRESS
    query_task.start = timezone.now()
    query_task.save()

    patient_name = re.sub(r"\s*,\s*", "^", query_task.patient_name)

    study_date = ""
    if query_task.study_date_start:
        if not query_task.study_date_end:
            study_date = query_task.study_date_start.strptime(DICOM_DATE_FORMAT) + "-"
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

    query_job = query_task.job

    connector: DicomConnector = query_job.source.dicomserver.create_connector()

    try:
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


@shared_task
def on_job_finished(query_task_status_list: List[str], query_job_id: int):
    query_job = BatchQueryJob.objects.get(id=query_job_id)
    finish_dicom_job(query_task_status_list, query_job)
    send_job_finished_mail(query_job)


@shared_task
def on_job_failed(*args, **kwargs):
    # The Celery documentation is wrong about the provided parameters and when
    # the callback is called. This function definition seems to work however.
    # See https://github.com/celery/celery/issues/3709
    celery_task_id = args[0]
    query_job = BatchQueryJob.objects.get(id=kwargs["job_id"])
    handle_job_failure(query_job, celery_task_id)
