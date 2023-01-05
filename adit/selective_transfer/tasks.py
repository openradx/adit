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
from .models import (
    SelectiveTransferJob,
    SelectiveTransferSettings,
    SelectiveTransferTask,
)

logger = get_task_logger(__name__)


class ProcessSelectiveTransferTask(ProcessDicomTask):
    dicom_task_class = SelectiveTransferTask
    app_settings_class = SelectiveTransferSettings

    def handle_dicom_task(self, dicom_task):
        return TransferExecutor(dicom_task, self).start()


process_selective_transfer_task = ProcessSelectiveTransferTask()

celery_app.register_task(process_selective_transfer_task)


class HandleFinishedSelectiveTransferJob(HandleFinishedDicomJob):
    dicom_job_class = SelectiveTransferJob
    send_job_finished_mail = False


handle_finished_selective_transfer_job = HandleFinishedSelectiveTransferJob()

celery_app.register_task(handle_finished_selective_transfer_job)


class HandleFailedSelectiveTransferJob(HandleFailedDicomJob):
    dicom_job_class = SelectiveTransferJob
    send_job_failed_mail = True


handle_failed_selective_transfer_job = HandleFailedSelectiveTransferJob()

celery_app.register_task(handle_failed_selective_transfer_job)


class ProcessSelectiveTransferJob(ProcessDicomJob):
    dicom_job_class = SelectiveTransferJob
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY
    process_dicom_task = process_selective_transfer_task
    handle_finished_dicom_job = handle_finished_selective_transfer_job
    handle_failed_dicom_job = handle_failed_selective_transfer_job


process_selective_transfer_job = ProcessSelectiveTransferJob()

celery_app.register_task(process_selective_transfer_job)
