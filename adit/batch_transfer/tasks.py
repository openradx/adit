from celery.utils.log import get_task_logger
from django.conf import settings

from adit.celery import app as celery_app
from adit.core.tasks import (
    HandleFailedDicomJob,
    HandleFinishedDicomJob,
    ProcessDicomJob,
    ProcessDicomTask,
)
from adit.core.utils.transfer_utils import TransferExecutor

from .models import BatchTransferJob, BatchTransferSettings, BatchTransferTask

logger = get_task_logger(__name__)


class ProcessBatchTransferTask(ProcessDicomTask):
    dicom_task_class = BatchTransferTask
    app_settings_class = BatchTransferSettings

    def handle_dicom_task(self, dicom_task):
        return TransferExecutor(dicom_task, self).start()


process_batch_transfer_task = ProcessBatchTransferTask()

celery_app.register_task(process_batch_transfer_task)


class HandleFinishedBatchTransferJob(HandleFinishedDicomJob):
    dicom_job_class = BatchTransferJob
    send_job_finished_mail = True


handle_finished_batch_transfer_job = HandleFinishedBatchTransferJob()

celery_app.register_task(handle_finished_batch_transfer_job)


class HandleFailedBatchTransferJob(HandleFailedDicomJob):
    dicom_job_class = BatchTransferJob
    send_job_failed_mail = True


handle_failed_batch_transfer_job = HandleFailedBatchTransferJob()

celery_app.register_task(handle_failed_batch_transfer_job)


class ProcessBatchTransferJob(ProcessDicomJob):
    dicom_job_class = BatchTransferJob
    default_priority = settings.CELERY_TASK_DEFAULT_PRIORITY
    urgent_priority = settings.CELERY_TASK_URGENT_PRIORITY
    process_dicom_task = process_batch_transfer_task
    handle_finished_dicom_job = handle_finished_batch_transfer_job
    handle_failed_dicom_job = handle_failed_batch_transfer_job


process_batch_transfer_job = ProcessBatchTransferJob()

celery_app.register_task(process_batch_transfer_job)
