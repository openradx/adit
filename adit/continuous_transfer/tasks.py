from celery.utils.log import get_task_logger
from django.conf import settings
from adit.celery import app as celery_app
from adit.core.tasks import (
    ProcessDicomJob,
    ProcessDicomTask,
    HandleFinishedDicomJob,
    HandleFailedDicomJob,
)
from .models import (
    ContinuousTransferSettings,
    ContinuousTransferJob,
    ContinuousTransferTask,
)

logger = get_task_logger(__name__)

logger = get_task_logger(__name__)


class ProcessContinuousTransferTask(ProcessDicomTask):
    dicom_task_class = ContinuousTransferTask
    app_settings_class = ContinuousTransferSettings

    def handle_dicom_task(self, dicom_task):
        raise NotImplementedError()


process_continuous_transfer_task = ProcessContinuousTransferTask()

celery_app.register_task(process_continuous_transfer_task)


class HandleFinishedContinuousTransferJob(HandleFinishedDicomJob):
    dicom_job_class = ContinuousTransferJob
    send_job_finished_mail = True


handle_finished_continuous_transfer_job = HandleFinishedContinuousTransferJob()

celery_app.register_task(handle_finished_continuous_transfer_job)


class HandleFailedContinuousTransferJob(HandleFailedDicomJob):
    dicom_job_class = ContinuousTransferJob
    send_job_failed_mail = True


handle_failed_continuous_transfer_job = HandleFailedContinuousTransferJob()

celery_app.register_task(handle_failed_continuous_transfer_job)


class ProcessContinuousTransferJob(ProcessDicomJob):
    dicom_job_class = ContinuousTransferJob
    default_priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.BATCH_TRANSFER_URGENT_PRIORITY
    process_dicom_task = process_continuous_transfer_task
    handle_finished_dicom_job = handle_finished_continuous_transfer_job
    handle_failed_dicom_job = handle_failed_continuous_transfer_job


process_continuous_transfer_job = ProcessContinuousTransferJob()

celery_app.register_task(process_continuous_transfer_job)
