from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from adit.core.utils.transfer_util import TransferUtil
from adit.core.utils.task_utils import (
    prepare_dicom_job,
    prepare_dicom_task,
    finish_dicom_job,
    handle_job_failure,
)
from .models import (
    SelectiveTransferSettings,
    SelectiveTransferJob,
    SelectiveTransferTask,
)

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
@prepare_dicom_job(SelectiveTransferJob, logger)
def selective_transfer(transfer_job):
    priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    if transfer_job.urgent:
        priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY

    transfers = [
        transfer_selected_dicoms.s(task.id).set(priority=priority)
        for task in transfer_job.tasks.all()
    ]

    chord(transfers)(
        on_job_finished.s(transfer_job.id).on_error(
            on_job_failed.s(job_id=transfer_job.id)
        )
    )


@shared_task(bind=True)
@prepare_dicom_task(SelectiveTransferTask, SelectiveTransferSettings, logger)
def transfer_selected_dicoms(transfer_task):
    transfer_util = TransferUtil(transfer_task.job, transfer_task)
    return transfer_util.start_transfer()


@shared_task(ignore_result=True)
@finish_dicom_job(SelectiveTransferJob, logger)
def on_job_finished(transfer_job):  # pylint: disable=unused-argument
    pass


@shared_task
@handle_job_failure(SelectiveTransferJob, logger)
def on_job_failed(transfer_job):  # pylint: disable=unused-argument
    pass
