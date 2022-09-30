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
    BatchQuerySettings,
    BatchQueryJob,
    BatchQueryTask,
)
from .utils.query_utils import QueryExecutor

logger = get_task_logger(__name__)


class ProcessBatchQueryTask(ProcessDicomTask):
    dicom_task_class = BatchQueryTask
    app_settings_class = BatchQuerySettings

    def handle_dicom_task(self, dicom_task):
        return QueryExecutor(dicom_task, self).start()


process_batch_query_task = ProcessBatchQueryTask()

celery_app.register_task(process_batch_query_task)


class HandleFinishedBatchQueryJob(HandleFinishedDicomJob):
    dicom_job_class = BatchQueryJob
    send_job_finished_mail = True


handle_finished_batch_query_job = HandleFinishedBatchQueryJob()

celery_app.register_task(handle_finished_batch_query_job)


class HandleFailedBatchQueryJob(HandleFailedDicomJob):
    dicom_job_class = BatchQueryJob
    send_job_failed_mail = True


handle_failed_batch_query_job = HandleFailedBatchQueryJob()

celery_app.register_task(handle_failed_batch_query_job)


class ProcessBatchQueryJob(ProcessDicomJob):
    dicom_job_class = BatchQueryJob
    default_priority = settings.BATCH_QUERY_DEFAULT_PRIORITY
    urgent_priority = settings.BATCH_QUERY_URGENT_PRIORITY
    process_dicom_task = process_batch_query_task
    handle_finished_dicom_job = handle_finished_batch_query_job
    handle_failed_dicom_job = handle_failed_batch_query_job


process_batch_query_job = ProcessBatchQueryJob()

celery_app.register_task(process_batch_query_job)
