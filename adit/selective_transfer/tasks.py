from django.conf import settings

from adit.celery import app as celery_app
from adit.core.tasks import (
    ProcessDicomJob,
    ProcessDicomTask,
)
from adit.core.utils.transfer_utils import TransferExecutor

from .models import (
    SelectiveTransferJob,
    SelectiveTransferSettings,
    SelectiveTransferTask,
)


class ProcessSelectiveTransferTask(ProcessDicomTask):
    dicom_task_class = SelectiveTransferTask
    app_settings_class = SelectiveTransferSettings

    def handle_dicom_task(self, dicom_task) -> tuple[SelectiveTransferTask.Status, str]:
        return TransferExecutor(dicom_task, self).start()


process_selective_transfer_task = ProcessSelectiveTransferTask()

celery_app.register_task(process_selective_transfer_task)


class ProcessSelectiveTransferJob(ProcessDicomJob):
    dicom_job_class = SelectiveTransferJob
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY
    process_dicom_task = process_selective_transfer_task


process_selective_transfer_job = ProcessSelectiveTransferJob()

celery_app.register_task(process_selective_transfer_job)
