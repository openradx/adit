from typing import List
from celery import shared_task, chord
from celery import Task as CeleryTask
from celery.utils.log import get_task_logger
from django.conf import settings
from adit.core.utils.transfer_utils import execute_transfer
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
def process_transfer_job(transfer_job_id: int):
    transfer_job = SelectiveTransferJob.objects.get(id=transfer_job_id)
    prepare_dicom_job(transfer_job)

    priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    if transfer_job.urgent:
        priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY

    transfers = [
        process_transfer_task.s(transfer_task.id).set(priority=priority)
        for transfer_task in transfer_job.tasks.all()
    ]

    chord(transfers)(
        on_job_finished.s(transfer_job.id).on_error(
            on_job_failed.s(job_id=transfer_job.id)
        )
    )


@shared_task(bind=True)
def process_transfer_task(self: CeleryTask, transfer_task_id: int):
    transfer_task = SelectiveTransferTask.objects.get(id=transfer_task_id)
    prepare_dicom_task(transfer_task, SelectiveTransferSettings.get(), self)
    return execute_transfer(transfer_task)


@shared_task(ignore_result=True)
def on_job_finished(transfer_task_status_list: List[str], transfer_job_id: int):
    transfer_job = SelectiveTransferJob.objects.get(id=transfer_job_id)
    finish_dicom_job(transfer_task_status_list, transfer_job)


@shared_task
def on_job_failed(*args, **kwargs):
    # The Celery documentation is wrong about the provided parameters and when
    # the callback is called. This function definition seems to work however.
    # See https://github.com/celery/celery/issues/3709
    celery_task_id = args[0]
    transfer_job = SelectiveTransferJob.objects.get(id=kwargs["job_id"])
    handle_job_failure(transfer_job, celery_task_id)
