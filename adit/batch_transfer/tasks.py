from django.conf import settings

from adit.celery import app as celery_app
from adit.core.tasks import (
    ProcessDicomJob,
    ProcessDicomTask,
)
from adit.core.utils.transfer_utils import TransferExecutor

from .models import BatchTransferJob, BatchTransferSettings, BatchTransferTask


class ProcessBatchTransferTask(ProcessDicomTask):
    dicom_task_class = BatchTransferTask
    app_settings_class = BatchTransferSettings

    def handle_dicom_task(self, dicom_task) -> tuple[BatchTransferTask.Status, str]:
        return TransferExecutor(dicom_task, self).start()


process_batch_transfer_task = ProcessBatchTransferTask()

celery_app.register_task(process_batch_transfer_task)


class ProcessBatchTransferJob(ProcessDicomJob):
    dicom_job_class = BatchTransferJob
    default_priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.BATCH_TRANSFER_URGENT_PRIORITY
    process_dicom_task = process_batch_transfer_task


process_batch_transfer_job = ProcessBatchTransferJob()

celery_app.register_task(process_batch_transfer_job)
