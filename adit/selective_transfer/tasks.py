from datetime import timedelta
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.contrib.humanize.templatetags.humanize import naturaltime
from adit.main.tasks import on_job_failed, transfer_dicoms
from adit.main.models import TransferTask
from .models import AppSettings, SelectiveTransferJob

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def selective_transfer(job_id):
    logger.info("Prepare selective transfer job with ID %d", job_id)

    job = SelectiveTransferJob.objects.get(id=job_id)

    if job.status != SelectiveTransferJob.Status.PENDING:
        raise AssertionError(f"Invalid job status: {job.get_status_display()}")

    transfers = [transfer_selected_dicoms.s(task.id) for task in job.tasks.all()]

    chord(transfers)(on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id)))


@shared_task(bind=True)
def transfer_selected_dicoms(self, task_id):
    logger.info(
        "Processing transfer task with ID %d in selective transfer job.", task_id
    )

    task = TransferTask.objects.get(id=task_id)

    if task.status != TransferTask.Status.PENDING:
        raise AssertionError(f"Invalid transfer task status: {task.status}")

    if task.job.status == SelectiveTransferJob.Status.CANCELING:
        task.status = TransferTask.Status.CANCELED
        task.save()
        return task.status

    app_settings = AppSettings.load()
    if app_settings.selective_transfer_suspended:
        eta = timezone.now + timedelta(minutes=5)
        raise self.retry(
            eta=eta,
            exc=Warning(
                f"Selective transfer suspended. Retrying in {naturaltime(eta)}."
            ),
        )

    return transfer_dicoms(task_id)


@shared_task(ignore_result=True)
def on_job_finished(task_status_list, job_id):
    logger.info("Selective transfer job with ID %d finished.", job_id)

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
            raise AssertionError("Invalid task status: " + status)

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
        raise AssertionError("Invalid task status: " + job.status)

    job.save()
