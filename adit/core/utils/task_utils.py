from logging import getLogger
from typing import List
from datetime import timedelta
from celery import Task as CeleryTask
from django.utils import timezone
from django.template.defaultfilters import pluralize
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

    if dicom_job.status == DicomJob.Status.CANCELING:
        dicom_job.status = DicomJob.Status.CANCELED
        num = dicom_task_status_list.count(DicomTask.Status.CANCELED)
        dicom_job.message = f"{num} task{pluralize(num)} canceled."
        dicom_job.save()
        return

    success = 0
    warning = 0
    failure = 0
    for status in dicom_task_status_list:
        if status == DicomTask.Status.SUCCESS:
            success += 1
        elif status == DicomTask.Status.WARNING:
            warning += 1
        elif status == DicomTask.Status.FAILURE:
            failure += 1
        else:
            raise AssertionError(
                f"Invalid dicom task result status in {dicom_job}: {status}"
            )

    if success and not warning and not failure:
        dicom_job.status = DicomJob.Status.SUCCESS
        dicom_job.message = "All tasks succeeded."
    elif success and warning and not failure:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "Some tasks with warnings."
    elif not success and warning and not failure:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "All tasks with warnings."
    elif success and failure or warning and failure:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "Some tasks failed."
    elif not success and not warning and failure:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "All tasks failed."
    else:
        raise AssertionError(f"At least one task of {dicom_job} must a valid state.")

    dicom_job.save()


def handle_job_failure(dicom_job: DicomJob, celery_task_id: int):
    logger.error("%s failed unexpectedly.", dicom_job)

    dicom_job.status = DicomJob.Status.FAILURE
    dicom_job.message = "Job failed unexpectedly."
    dicom_job.save()

    send_job_failed_mail(dicom_job, celery_task_id)
