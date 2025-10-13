import logging
import subprocess
import traceback
from concurrent import futures
from time import sleep
from typing import cast

import pglock
from django import db
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from pebble import ProcessFuture, concurrent
from procrastinate import JobContext, RetryStrategy
from procrastinate.contrib.django import app

from .errors import DicomError, RetriableDicomError
from .models import DicomFolder, DicomJob, DicomTask
from .types import ProcessingResult
from .utils.db_utils import ensure_db_connection
from .utils.mail import send_mail_to_admins
from .utils.task_utils import get_dicom_processor, get_dicom_task

DISTRIBUTED_LOCK = "process_dicom_task_lock"

logger = logging.getLogger(__name__)


@app.periodic(cron="0 7 * * *")  # every day at 7am
@app.task
def check_disk_space(*args, **kwargs):
    # TODO: Maybe only check active folders (that belong to an institute and are active
    # as a destination)
    folders = DicomFolder.objects.all()
    for folder in folders:
        size = int(subprocess.check_output(["du", "-sm", folder.path]).split()[0].decode("utf-8"))
        size = size / 1024  # convert MB to GB
        if folder.warn_size is not None and size > folder.warn_size:
            quota = "?"
            if folder.quota is not None:
                quota = folder.quota
            msg = (
                f"Low disk space of destination folder: {folder.name}\n"
                f"{size} GB of {quota} GB used."
            )
            logger.warning(msg)
            send_mail_to_admins("Warning, low disk space!", msg)


@app.periodic(cron="0 3 * * * ")  # every day at 3am
@app.task
def backup_db(*args, **kwargs):
    call_command("dbbackup", "--clean", "-v 2")


@app.task(
    queue="dicom",
    pass_context=True,
    # TODO: Increase the priority slightly when it will be retried
    # See https://github.com/procrastinate-org/procrastinate/issues/1096
    retry=RetryStrategy(
        max_attempts=settings.DICOM_TASK_MAX_ATTEMPTS,
        exponential_wait=settings.DICOM_TASK_EXPONENTIAL_WAIT,
        retry_exceptions={RetriableDicomError},
    ),
)
def process_dicom_task(context: JobContext, model_label: str, task_id: int):
    assert context.job

    dicom_task = get_dicom_task(model_label, task_id)
    assert dicom_task.status == DicomTask.Status.PENDING

    # When the first DICOM task of a job is processed then the status of the
    # job switches from PENDING to IN_PROGRESS
    dicom_job = dicom_task.job
    if dicom_job.status == DicomJob.Status.PENDING:
        dicom_job.status = DicomJob.Status.IN_PROGRESS
        dicom_job.start = timezone.now()
        dicom_job.save()
        logger.info(f"Processing of {dicom_job} started.")

    dicom_task.status = DicomTask.Status.IN_PROGRESS
    dicom_task.start = timezone.now()
    dicom_task.attempts += 1
    dicom_task.save()

    logger.info(f"Processing of {dicom_task} started.")

    @concurrent.process(timeout=settings.DICOM_TASK_PROCESS_TIMEOUT, daemon=True)
    def _process_dicom_task(model_label: str, task_id: int) -> ProcessingResult:
        dicom_task = get_dicom_task(model_label, task_id)
        processor = get_dicom_processor(dicom_task)

        logger.info(f"Start processing of {dicom_task}.")
        return processor.process()

    @concurrent.thread()
    def _monitor_task(context: JobContext, future: ProcessFuture) -> None:
        while not future.done():
            if context.should_abort():
                future.cancel()
                sleep(settings.DICOM_TASK_CANCELED_MONITOR_INTERVAL)
        db.close_old_connections()

    try:
        future = cast(ProcessFuture, _process_dicom_task(model_label, task_id))
        _monitor_task(context, future)
        result: ProcessingResult = future.result()
        dicom_task.status = result["status"]
        dicom_task.message = result["message"]
        dicom_task.log = result["log"]
        ensure_db_connection()

    except futures.TimeoutError:
        dicom_task.message = "Task was aborted due to timeout."
        dicom_task.status = DicomTask.Status.FAILURE
        ensure_db_connection()

    except RetriableDicomError as err:
        logger.exception("Retriable error occurred during %s.", dicom_task)

        # Cave, the the attempts of the Procrastinate job must not be the same number
        # as the attempts of the DicomTask. The DicomTask could be started by multiple
        # Procrastinate jobs (e.g. if the user canceled and resumed the same task).
        if context.job.attempts < settings.DICOM_TASK_MAX_ATTEMPTS:
            dicom_task.status = DicomTask.Status.PENDING
            dicom_task.message = "Task failed, but will be retried."
            if dicom_task.log:
                dicom_task.log += "\n"
            dicom_task.log += str(err)
        else:
            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)

        ensure_db_connection()
        raise err

    except Exception as err:
        if isinstance(err, DicomError):
            logger.exception("Error during %s.", dicom_task)
        else:
            logger.exception("Unexpected error during %s.", dicom_task)

        dicom_task.status = DicomTask.Status.FAILURE
        dicom_task.message = str(err)
        if dicom_task.log:
            dicom_task.log += "\n---\n"
        dicom_task.log += traceback.format_exc()

        ensure_db_connection()

    finally:
        dicom_task.end = timezone.now()
        dicom_task.save()
        logger.info(f"Processing of {dicom_task} ended.")

        with pglock.advisory(DISTRIBUTED_LOCK):
            dicom_job.refresh_from_db()
            job_finished = dicom_job.post_process()

        if job_finished:
            logger.info(f"Processing of {dicom_job} ended.")

        # TODO: https://github.com/procrastinate-org/procrastinate/issues/1106
        db.close_old_connections()
