from adit.core.utils.dicom_connector import DicomConnector
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from adit.core.utils.mail import send_job_finished_mail
from adit.core.utils.task_utils import (
    prepare_dicom_job,
    prepare_dicom_task,
    finish_dicom_job,
    handle_job_failure,
    fetch_patient_id_cached,
)
from .models import StudyFinderJob, StudyFinderQuery, StudyFinderSettings

logger = get_task_logger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


@shared_task(ignore_result=True)
@prepare_dicom_job(StudyFinderJob, logger)
def find_studies(finder_job: StudyFinderJob):
    priority = settings.STUDY_TRANSFER_DEFAULT_PRIORITY
    if finder_job.urgent:
        priority = settings.STUDY_TRANSFER_URGENT_PRIORITY

    process_queries = [
        process_query.s(query.id).set(priority=priority)
        for query in finder_job.queries.all()
    ]

    chord(process_queries)(
        on_job_finished.s(finder_job.id).on_error(on_job_failed.s(job_id=finder_job.id))
    )


@shared_task(bind=True)
@prepare_dicom_task(StudyFinderQuery, StudyFinderSettings, logger)
def process_query(query: StudyFinderQuery):
    job = query.job

    query.status = StudyFinderQuery.Status.IN_PROGRESS
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

        for study in studies:
            pass

    except Exception as err:
        pass
    finally:
        query.end = timezone.now()
        query.save()


@shared_task
@finish_dicom_job(StudyFinderJob, logger)
def on_job_finished(finder_job: StudyFinderJob):
    send_job_finished_mail(finder_job)


@shared_task
@handle_job_failure(StudyFinderJob, logger)
def on_job_failed(finder_job):  # pylint: disable=unused-argument
    pass