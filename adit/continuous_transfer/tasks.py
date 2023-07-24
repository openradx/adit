from celery.utils.log import get_task_logger
from django.conf import settings

from adit.celery import app as celery_app
from adit.core.models import DicomJob
from adit.core.tasks import (
    HandleFailedDicomJob,
    HandleFinishedDicomJob,
    ProcessDicomJob,
    ProcessDicomTask,
)
from adit.core.utils.transfer_utils import TransferExecutor

from .models import (
    ContinuousQueryTask,
    ContinuousTransferJob,
    ContinuousTransferSettings,
    ContinuousTransferTask,
)

logger = get_task_logger(__name__)


class ProcessContinuousQueryTask(ProcessDicomTask):
    dicom_task_class = ContinuousQueryTask
    app_settings_class = ContinuousTransferSettings

    def handle_dicom_task(self, dicom_task: ContinuousQueryTask):
        last_processed = dicom_task.job.last_processed


class ProcessContinuousTransferTask(ProcessDicomTask):
    dicom_task_class = ContinuousTransferTask
    app_settings_class = ContinuousTransferSettings

    def handle_dicom_task(self, dicom_task):
        return TransferExecutor(dicom_task, self).start()
        # TODO: Fire up ContiuousTransferJob to query for newer studies


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
    default_priority = settings.CONTINUOUS_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.CONTINUOUS_TRANSFER_URGENT_PRIORITY
    process_dicom_task = process_continuous_transfer_task
    handle_finished_dicom_job = handle_finished_continuous_transfer_job
    handle_failed_dicom_job = handle_failed_continuous_transfer_job

    def run(self, dicom_job_id: int):
        dicom_job = ContinuousTransferJob.objects.get(id=dicom_job_id)

        logger.info("Proccessing %s.", dicom_job)

        if dicom_job.status != ContinuousTransferJob.Status.PENDING:
            raise AssertionError(f"Invalid {dicom_job} status: {dicom_job.get_status_display()}")

        # TODO:
        # - Make query and get first result (respect last_transfer)
        # - Delay transfer task if result is not None
        # - If result None and study_date_end is present then job is finished
        # - If result None and study_date_end is not present then rerun job in a day or so


process_continuous_transfer_job = ProcessContinuousTransferJob()

celery_app.register_task(process_continuous_transfer_job)
