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
    BatchFinderJob,
    BatchFinderQuery,
    BatchFinderResult,
    BatchFinderSettings,
)

logger = get_task_logger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


@shared_task(ignore_result=True)
@prepare_dicom_job(BatchFinderJob, logger)
def find_studies(finder_job: BatchFinderJob):
    priority = settings.BATCH_FINDER_DEFAULT_PRIORITY
    if finder_job.urgent:
        priority = settings.BATCH_FINDER_URGENT_PRIORITY

    process_queries = [
        process_query.s(query.id).set(priority=priority)
        for query in finder_job.queries.all()
    ]

    chord(process_queries)(
        on_job_finished.s(finder_job.id).on_error(on_job_failed.s(job_id=finder_job.id))
    )


@shared_task(bind=True)
@prepare_dicom_task(BatchFinderQuery, BatchFinderSettings, logger)
def process_query(query: BatchFinderQuery):
    job = query.job

    query.status = BatchFinderQuery.Status.IN_PROGRESS
    query.start = timezone.now()
    query.save()

    try:
        connector: DicomConnector = job.source.dicomserver.create_connector()

        patient_id = fetch_patient_id_cached(
            connector,
            query.patient_id,
            query.patient_name,
            query.patient_birth_date,
        )

        study_date = ""
        if query.study_date_start:
            if not query.study_date_end:
                study_date = query.study_date_start.strptime(DICOM_DATE_FORMAT) + "-"
            elif query.study_date_start == query.study_date_end:
                study_date = query.study_date_start.strptime(DICOM_DATE_FORMAT)
            else:
                study_date = (
                    query.study_date_start.strptime(DICOM_DATE_FORMAT)
                    + "-"
                    + query.study_date_end.strptime(DICOM_DATE_FORMAT)
                )
        elif query.study_date_end:
            study_date = "-" + query.study_date_end.strptime(DICOM_DATE_FORMAT)

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
                "ModalitiesInStudy": query.modalities,
                "NumberOfStudyRelatedInstances": "",
            }
        )

        results = []
        for study in studies:
            result = BatchFinderResult(
                job=job,
                query=query,
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

        BatchFinderResult.objects.bulk_create(results)

        if results:
            query.status = BatchFinderQuery.Status.SUCCESS
            query.message = f"Found {len(results)} studies."
        else:
            query.status = BatchFinderQuery.Status.WARNING
            query.message = "No studies found."
    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Error during %s", query)
        query.status = BatchFinderQuery.Status.FAILURE
        query.message = str(err)
    finally:
        query.end = timezone.now()
        query.save()

    return query.status


@shared_task
@finish_dicom_job(BatchFinderJob, logger)
def on_job_finished(finder_job: BatchFinderJob):
    send_job_finished_mail(finder_job)


@shared_task
@handle_job_failure(BatchFinderJob, logger)
def on_job_failed(finder_job):  # pylint: disable=unused-argument
    pass
