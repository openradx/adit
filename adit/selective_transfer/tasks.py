from datetime import timedelta
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from django.contrib.humanize.templatetags.humanize import naturaltime
from adit.core.models import TransferTask
from adit.core.tasks import on_job_failed, transfer_dicoms
from adit.core.utils.scheduler import Scheduler
from .models import SelectiveTransferSettings, SelectiveTransferJob

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
    if job.transfer_urgently:
        priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY

    transfers = [
        transfer_selected_dicoms.s(task.id).set(priority=priority)
        for task in job.tasks.all()
    ]

    chord(transfers)(on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id)))


@shared_task(bind=True)
def transfer_selected_dicoms(self, task_id):
    transfer_task = TransferTask.objects.get(id=task_id)
    job = transfer_task.job

    logger.info(
        "Processing selective transfer task [Job ID %d, Task ID %d].",
        job.id,
        transfer_task.id,
    )

    if transfer_task.status != TransferTask.Status.PENDING:
        raise AssertionError(
            "Invalid selective transfer task processing status "
            f"{transfer_task.get_status_display()} "
            f"[Job ID {job.id}, Task ID {transfer_task.id}]."
        )

    if job.status == SelectiveTransferJob.Status.CANCELING:
        transfer_task.status = TransferTask.Status.CANCELED
        transfer_task.end = timezone.now()
        transfer_task.save()
        return transfer_task.status

    _check_can_run_now(self, transfer_task)

    if job.status == SelectiveTransferJob.Status.PENDING:
        job.status = SelectiveTransferJob.Status.IN_PROGRESS
        job.start = timezone.now()
        job.save()

    return transfer_dicoms(task_id)


@shared_task(ignore_result=True)
def on_job_finished(task_status_list, job_id):
    logger.info("Selective transfer job finished [Job ID %d].", job_id)

    job = SelectiveTransferJob.objects.get(id=job_id)

    if (
        job.status == SelectiveTransferJob.Status.CANCELING
        and TransferTask.Status.CANCELED in task_status_list
    ):
        job.status = SelectiveTransferJob.Status.CANCELED
        job.save()
        return

    has_success = False
    has_failure = False
    for status in task_status_list:
        if status == TransferTask.Status.SUCCESS:
            has_success = True
        elif status == TransferTask.Status.FAILURE:
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

    if not transfer_task.job.transfer_urgently:
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
