from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from adit.core.utils.transfer_util import TransferUtil
from adit.core.utils.mail import send_job_finished_mail
from adit.core.utils.task_utils import (
    prepare_dicom_job,
    prepare_dicom_task,
    finish_dicom_job,
    handle_job_failure,
)
from .models import (
    BatchTransferSettings,
    BatchTransferJob,
    BatchTransferTask,
)

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
@prepare_dicom_job(BatchTransferJob, logger)
def batch_transfer(transfer_job: BatchTransferJob):
    priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    if transfer_job.urgent:
        priority = settings.BATCH_TRANSFER_URGENT_PRIORITY

    transfer_tasks = [
        transfer_dicoms.s(transfer_task.id).set(priority=priority)
        for transfer_task in transfer_job.tasks.all()
    ]

    chord(transfer_tasks)(
        on_job_finished.s(transfer_job.id).on_error(
            on_job_failed.s(job_id=transfer_job.id)
        )
    )


@shared_task(bind=True)
@prepare_dicom_task(BatchTransferTask, BatchTransferSettings, logger)
def transfer_dicoms(transfer_task: BatchTransferTask):
    transfer_util = TransferUtil(transfer_task)
    return transfer_util.start_transfer()


@shared_task(ignore_result=True)
@finish_dicom_job(BatchTransferJob, logger)
def on_job_finished(transfer_job: BatchTransferJob):
    send_job_finished_mail(transfer_job)


@shared_task
@handle_job_failure(BatchTransferJob, logger)
def on_job_failed(transfer_job: BatchTransferJob):  # pylint: disable=unused-argument
    pass
