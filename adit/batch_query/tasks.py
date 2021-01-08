from typing import List
from celery import shared_task, chord
from celery import Task as CeleryTask
from celery.utils.log import get_task_logger
from django.conf import settings
from adit.core.utils.mail import send_job_finished_mail
from adit.core.utils.task_utils import (
    prepare_dicom_job,
    prepare_dicom_task,
    finish_dicom_job,
    handle_job_failure,
)
from .models import (
    BatchQueryJob,
    BatchQueryTask,
    BatchQuerySettings,
)
from .utils.query_utils import execute_query

logger = get_task_logger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


@shared_task(ignore_result=True)
def process_query_job(query_job_id: int):
    query_job = BatchQueryJob.objects.get(id=query_job_id)
    prepare_dicom_job(query_job)

    priority = settings.BATCH_QUERY_DEFAULT_PRIORITY
    if query_job.urgent:
        priority = settings.BATCH_QUERY_URGENT_PRIORITY

    process_query_tasks = [
        process_query_task.s(query_task.id).set(priority=priority)
        for query_task in query_job.tasks.all()
    ]

    chord(process_query_tasks)(
        on_job_finished.s(query_job.id).on_error(on_job_failed.s(job_id=query_job.id))
    )


@shared_task(bind=True)
def process_query_task(self: CeleryTask, query_task_id: BatchQueryTask):
    query_task = BatchQueryTask.objects.get(id=query_task_id)
    prepare_dicom_task(query_task, BatchQuerySettings.get(), self)
    return execute_query(query_task)


@shared_task
def on_job_finished(query_task_status_list: List[str], query_job_id: int):
    query_job = BatchQueryJob.objects.get(id=query_job_id)
    finish_dicom_job(query_task_status_list, query_job)
    send_job_finished_mail(query_job)


@shared_task
def on_job_failed(*args, **kwargs):
    # The Celery documentation is wrong about the provided parameters and when
    # the callback is called. This function definition seems to work however.
    # See https://github.com/celery/celery/issues/3709
    celery_task_id = args[0]
    query_job = BatchQueryJob.objects.get(id=kwargs["job_id"])
    handle_job_failure(query_job, celery_task_id)
