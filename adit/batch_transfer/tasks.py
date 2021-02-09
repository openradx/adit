from typing import List
from celery import shared_task, chord
from celery import Task as CeleryTask
from celery.utils.log import get_task_logger
from django.conf import settings
from adit.core.utils.transfer_utils import execute_transfer
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
def process_transfer_job(transfer_job_id: int):
    transfer_job = BatchTransferJob.objects.get(id=transfer_job_id)
    prepare_dicom_job(transfer_job)

    priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    if transfer_job.urgent:
        priority = settings.BATCH_TRANSFER_URGENT_PRIORITY

    transfer_tasks = transfer_job.tasks.filter(status=BatchTransferTask.Status.PENDING)

    process_transfer_tasks = [
        process_transfer_task.s(transfer_task.id).set(priority=priority)
        for transfer_task in transfer_tasks
    ]

    chord(process_transfer_tasks)(
        on_job_finished.s(transfer_job.id).on_error(
            on_job_failed.s(job_id=transfer_job.id)
        )
    )


@shared_task(bind=True)
def process_transfer_task(self: CeleryTask, transfer_task_id: int):
    transfer_task = BatchTransferTask.objects.get(id=transfer_task_id)
    prepare_dicom_task(transfer_task, BatchTransferSettings.get(), celery_task=self)
    return execute_transfer(transfer_task, celery_task=self)


@shared_task(ignore_result=True)
def on_job_finished(transfer_task_status_list: List[str], transfer_job_id: int):
    transfer_job = BatchTransferJob.objects.get(id=transfer_job_id)
    finish_dicom_job(transfer_task_status_list, transfer_job)
    send_job_finished_mail(transfer_job)


@shared_task
def on_job_failed(*args, **kwargs):
    # The Celery documentation is wrong about the provided parameters and when
    # the callback is called. This function definition seems to work however.
    # See https://github.com/celery/celery/issues/3709
    celery_task_id = args[0]
    transfer_job = BatchTransferJob.objects.get(id=kwargs["job_id"])
    handle_job_failure(transfer_job, celery_task_id)
