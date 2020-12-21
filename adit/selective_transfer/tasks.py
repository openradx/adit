from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from adit.core.utils.transfer_util import TransferUtil
from adit.core.utils import task_utils
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

    task_utils.precheck_job(job)

    priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    if job.urgent:
        priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY

    transfers = [
        transfer_selected_dicoms.s(task.id).set(priority=priority)
        for task in job.tasks.all()
    ]

    chord(transfers)(on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id)))


@shared_task(bind=True)
# @task_utils.prepare_dicom_task(SelectiveTransferTask, SelectiveTransferSettings, logger)
def transfer_selected_dicoms(self, task_id):
    transfer_task = SelectiveTransferTask.objects.get(id=task_id)
    job = transfer_task.job

    logger.info(
        "Processing selective transfer task [Job ID %d, Task ID %d].",
        job.id,
        transfer_task.id,
    )

    task_utils.precheck_task(transfer_task)

    canceled_status = task_utils.check_canceled(job, transfer_task)
    if canceled_status:
        return canceled_status

    task_utils.check_can_run_now(
        self, SelectiveTransferSettings.get(), job, transfer_task
    )

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
