from logging import getLogger
from typing import List
from datetime import timedelta
from celery import Task as CeleryTask
from django.utils import timezone
from adit.core.utils.mail import send_job_failed_mail
from ..models import AppSettings, DicomJob, DicomTask
from ..utils.scheduler import Scheduler


logger = getLogger(__name__)


def prepare_dicom_job(dicom_job: DicomJob):
    logger.info("Proccessing %s.", dicom_job)

    if dicom_job.status != DicomJob.Status.PENDING:
        raise AssertionError(
            f"Invalid {dicom_job} status: {dicom_job.get_status_display()}"
        )


def prepare_dicom_task(
    dicom_task: DicomTask, app_settings: AppSettings, celery_task: CeleryTask
):
    logger.info("Processing %s.", dicom_task)

    if dicom_task.status != DicomTask.Status.PENDING:
        raise AssertionError(
            f"Invalid {dicom_task} status: {dicom_task.get_status_display()}"
        )

    dicom_job = dicom_task.job

    if dicom_job.status == DicomJob.Status.CANCELING:
        dicom_task.status = DicomTask.Status.CANCELED
        dicom_task.end = timezone.now()
        dicom_task.save()
        return

    if not dicom_job.urgent:
        scheduler = Scheduler(
            app_settings.slot_begin_time,
            app_settings.slot_end_time,
        )
        if scheduler.must_be_scheduled():
            raise celery_task.retry(
                eta=scheduler.next_slot(),
                exc=Warning(f"Outside of time slot. Rescheduling {dicom_task}"),
            )

    if app_settings.suspended:
        raise celery_task.retry(
            eta=timezone.now() + timedelta(minutes=60),
            exc=Warning(f"App suspended. Rescheduling {dicom_task}."),
        )

    if dicom_job.status == DicomJob.Status.PENDING:
        dicom_job.status = DicomJob.Status.IN_PROGRESS
        dicom_job.start = timezone.now()
        dicom_job.save()


def finish_dicom_job(dicom_task_status_list: List[str], dicom_job: DicomJob):
    logger.info("%s finished.", dicom_job)

    if (
        dicom_job.status == DicomJob.Status.CANCELING
        and DicomJob.Status.CANCELED in dicom_task_status_list
    ):
        dicom_job.status = DicomJob.Status.CANCELED
        dicom_job.save()
        return

    has_success = False
    has_failure = False
    for status in dicom_task_status_list:
        if status == DicomTask.Status.SUCCESS:
            has_success = True
        elif status == DicomTask.Status.FAILURE:
            has_failure = True
        else:
            raise AssertionError(
                f"Invalid dicom task result status in {dicom_job}: {status}"
            )

    if has_success and has_failure:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "Some transfer tasks failed."
    elif has_success:
        dicom_job.status = DicomJob.Status.SUCCESS
        dicom_job.message = "All transfer tasks succeeded."
    elif has_failure:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "All transfer tasks failed."
    else:
        raise AssertionError(f"At least one task of {dicom_job} must succeed or fail.")

    dicom_job.save()


def handle_job_failure(dicom_job: DicomJob, celery_task_id: int):
    logger.error("%s failed unexpectedly.", dicom_job)

    dicom_job.status = DicomJob.Status.FAILURE
    dicom_job.message = "Failed unexpectedly."
    dicom_job.save()

    send_job_failed_mail(dicom_job, celery_task_id)
