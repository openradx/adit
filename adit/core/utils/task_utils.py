import logging
import io
from typing import List, Tuple
from datetime import timedelta
from celery import Task as CeleryTask
from django.utils import timezone
from django.template.defaultfilters import pluralize
from adit.core.utils.mail import send_job_failed_mail
from ..models import AppSettings, DicomJob, DicomTask
from ..utils.scheduler import Scheduler


logger = logging.getLogger(__name__)


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

    successes = 0
    warnings = 0
    failures = 0
    for status in dicom_task_status_list:
        if status == DicomTask.Status.SUCCESS:
            successes += 1
        elif status == DicomTask.Status.WARNING:
            warnings += 1
        elif status == DicomTask.Status.FAILURE:
            failures += 1
        else:
            raise AssertionError(
                f"Invalid dicom task result status in {dicom_job}: {status}"
            )

    if successes and not warnings and not failures:
        dicom_job.status = DicomJob.Status.SUCCESS
        dicom_job.message = "All tasks succeeded."
    elif successes and warnings and not failures:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "Some tasks with warnings."
    elif not successes and warnings and not failures:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "All tasks with warnings."
    elif successes and failures or warnings and failures:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "Some tasks failed."
    elif not successes and not warnings and failures:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "All tasks failed."
    else:
        raise AssertionError(f"Invalid task status list of {dicom_job}.")

    dicom_job.save()


def handle_job_failure(dicom_job: DicomJob, celery_task_id: int):
    logger.error("%s failed unexpectedly.", dicom_job)

    dicom_job.status = DicomJob.Status.FAILURE
    dicom_job.message = "Job failed unexpectedly."
    dicom_job.save()

    send_job_failed_mail(dicom_job, celery_task_id)


def hijack_logger(my_logger) -> Tuple[logging.StreamHandler, io.StringIO]:
    """Intercept all logger messages to save them later to the task."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    my_logger.parent.addHandler(handler)
    return handler, stream


def store_log_in_task(
    my_logger: logging.Logger,
    handler: logging.StreamHandler,
    stream: io.StringIO,
    dicom_task: DicomTask,
) -> None:
    handler.flush()
    if dicom_task.log:
        dicom_task.log += "\n" + stream.getvalue()
    else:
        dicom_task.log = stream.getvalue()
    stream.close()
    my_logger.parent.removeHandler(handler)
