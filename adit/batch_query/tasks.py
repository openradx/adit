from celery import shared_task, chord
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
    fetch_patient_id_cached,
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
@prepare_dicom_job(BatchQueryJob, logger)
def find_studies(query_job: BatchQueryJob):
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
@prepare_dicom_task(BatchQueryTask, BatchQuerySettings, logger)
def process_query(query_task: BatchQueryTask):
    job = query_task.job

    query_task.status = BatchQueryTask.Status.IN_PROGRESS
    query_task.start = timezone.now()
    query_task.save()

    try:
        connector: DicomConnector = job.source.dicomserver.create_connector()

        patient_id = fetch_patient_id_cached(
            connector,
            query_task.patient_id,
            query_task.patient_name,
            query_task.patient_birth_date,
        )

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

        studies = connector.find_studies(
            {
                "PatientID": patient_id,
                "PatientName": "",
                "PatientBirthDate": "",
                "StudyInstanceUID": "",
                "AccessionNumber": "",
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
                job=job,
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
@finish_dicom_job(BatchQueryJob, logger)
def on_job_finished(query_job: BatchQueryJob):
    send_job_finished_mail(query_job)


@shared_task
@handle_job_failure(BatchQueryJob, logger)
def on_job_failed(query_job):  # pylint: disable=unused-argument
    pass
