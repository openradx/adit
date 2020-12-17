from datetime import timedelta
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from django.contrib.humanize.templatetags.humanize import naturaltime
from adit.core.utils.scheduler import Scheduler
from adit.core.utils.transfer_util import TransferUtil
from adit.core.utils.mail import send_job_failed_mail
from .models import (
    SelectiveTransferSettings,
    SelectiveTransferJob,
    SelectiveTransferTask,
)

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def selective_transfer(job_id):
    logger.info("Prepare selective transfer job [Job ID %d].", job_id)

    job = SelectiveTransferJob.objects.get(id=job_id)

    if job.status != SelectiveTransferJob.Status.PENDING:
        raise AssertionError(
            f"Invalid selective transfer job status {job.get_status_display()} "
            f"[Job ID {job.id}]."
        )

    priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    if job.urgent:
        priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY

    transfers = [
        transfer_selected_dicoms.s(task.id).set(priority=priority)
        for task in job.tasks.all()
    ]

    chord(transfers)(on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id)))


@shared_task(bind=True)
def transfer_selected_dicoms(self, task_id):
    transfer_task = SelectiveTransferTask.objects.get(id=task_id)
    job = transfer_task.job

    logger.info(
        "Processing selective transfer task [Job ID %d, Task ID %d].",
        job.id,
        transfer_task.id,
    )

    if transfer_task.status != SelectiveTransferTask.Status.PENDING:
        raise AssertionError(
            "Invalid selective transfer task processing status "
            f"{transfer_task.get_status_display()} "
            f"[Job ID {job.id}, Task ID {transfer_task.id}]."
        )

    if job.status == SelectiveTransferJob.Status.CANCELING:
        transfer_task.status = SelectiveTransferTask.Status.CANCELED
        transfer_task.end = timezone.now()
        transfer_task.save()
        return transfer_task.status

    _check_can_run_now(self, transfer_task)

    if job.status == SelectiveTransferJob.Status.PENDING:
        job.status = SelectiveTransferJob.Status.IN_PROGRESS
        job.start = timezone.now()
        job.save()

    transfer_util = TransferUtil(job, transfer_task)
    return transfer_util.start_transfer()


@shared_task(ignore_result=True)
def on_job_finished(task_status_list, job_id):
    logger.info("Selective transfer job finished [Job ID %d].", job_id)

    job = SelectiveTransferJob.objects.get(id=job_id)

    if (
        job.status == SelectiveTransferJob.Status.CANCELING
        and SelectiveTransferTask.Status.CANCELED in task_status_list
    ):
        job.status = SelectiveTransferJob.Status.CANCELED
        job.save()
        return

    has_success = False
    has_failure = False
    for status in task_status_list:
        if status == SelectiveTransferTask.Status.SUCCESS:
            has_success = True
        elif status == SelectiveTransferTask.Status.FAILURE:
            has_failure = True
        else:
            raise AssertionError(
                f"Invalid selective transfer task result status {status} [Job ID {job.id}]."
            )

    if has_success and has_failure:
        job.status = SelectiveTransferJob.Status.WARNING
        job.message = "Some transfer tasks failed."
    elif has_success:
        job.status = SelectiveTransferJob.Status.SUCCESS
        job.message = "All transfer tasks succeeded."
    elif has_failure:
        job.status = SelectiveTransferJob.Status.FAILURE
        job.message = "All transfer tasks failed."
    else:
        raise AssertionError(
            f"At least one request must succeed or fail [Job ID {job.id}]."
        )

    job.save()


def _check_can_run_now(celery_task, transfer_task):
    selective_transfer_settings = SelectiveTransferSettings.get()

    if not transfer_task.job.urgent:
        scheduler = Scheduler(
            selective_transfer_settings.slot_begin_time,
            selective_transfer_settings.slot_end_time,
        )
        if scheduler.must_be_scheduled():
            raise celery_task.retry(
                eta=scheduler.next_slot(),
                exc=Warning(
                    f"Selective transfer outside of time slot. "
                    f"[Job ID {transfer_task.job.id}, Task ID {transfer_task.id}]"
                ),
            )

    if selective_transfer_settings.suspended:
        eta = timezone.now() + timedelta(minutes=60)
        raise celery_task.retry(
            eta=eta,
            exc=Warning(
                f"Selective transfer suspended. Retrying in {naturaltime(eta)} "
                f"[Job ID {transfer_task.job.id}, Task ID {transfer_task.id}]."
            ),
        )


# The Celery documentation is wrong about the provided parameters and when
# the callback is called. This function definition seems to work however.
# See https://github.com/celery/celery/issues/3709
@shared_task
def on_job_failed(*args, **kwargs):
    celery_task_id = args[0]
    job_id = kwargs["job_id"]

    logger.error("Transfer job failed unexpectedly. [Job ID %d]", job_id)

    job = SelectiveTransferJob.objects.get(id=job_id)

    job.status = SelectiveTransferJob.Status.FAILURE
    job.message = "Selective transfer job failed unexpectedly."
    job.save()

    send_job_failed_mail(job, celery_task_id)
