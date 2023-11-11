import logging
import traceback
from datetime import timedelta

import humanize
import redis
from django import db
from django.conf import settings
from django.utils import timezone

from .errors import DicomConnectionError, OutOfDiskSpaceError
from .models import AppSettings, DicomJob, DicomTask, QueuedTask
from .types import DicomLogEntry
from .utils.job_utils import update_job_status
from .utils.mail import send_job_finished_mail

logger = logging.getLogger(__name__)

MAX_PRIORITY = 10


class ProcessDicomTask:
    dicom_task_class: type[DicomTask]
    app_settings_class: type[AppSettings]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._redis = redis.Redis.from_url(settings.REDIS_URL)

    def run(self, queued_task: QueuedTask) -> None:
        dicom_task = queued_task.content_object
        assert isinstance(dicom_task, self.dicom_task_class)

        app_settings = self.app_settings_class.get()
        assert app_settings

        if app_settings.suspended:
            delta = timedelta(minutes=60)
            queued_task.eta = timezone.now() + delta
            queued_task.save()

            logger.info(
                f"App suspended. Rescheduling {dicom_task} in {humanize.naturaldelta(delta)}."
            )
            return

        try:
            status, message, logs = self.process_dicom_task(dicom_task)
            dicom_task.status = status
            dicom_task.message = message
            dicom_task.log = "\n".join([log["message"] for log in logs])
        except (DicomConnectionError, OutOfDiskSpaceError) as err:
            # Inside the handle_dicom_task errors of kind RetriableTaskError can be raised
            # which are handled here and also raise a Retry in the end.
            logger.exception("Retriable error occurred during %s.", dicom_task)

            # We can't use the Celery built-in max_retries and celery_task.request.retries
            # directly as we also use celery_task.retry() for scheduling tasks.
            if dicom_task.retries < settings.DICOM_TASK_RETRIES:
                delta = (
                    timedelta(hours=24)
                    if isinstance(err, OutOfDiskSpaceError)
                    else timedelta(minutes=15)
                )
                logger.info(f"Retrying {dicom_task} in {humanize.naturaldelta(delta)}.")

                dicom_task.status = DicomTask.Status.PENDING
                dicom_task.message = "Task timed out and will be retried."
                if dicom_task.log:
                    dicom_task.log += "\n"
                dicom_task.log += str(err)

                dicom_task.retries += 1

                # Increase the priority slightly to make sure the task will be retried soon
                priority = queued_task.priority
                if priority < MAX_PRIORITY:
                    queued_task.priority = priority + 1
                    queued_task.eta = timezone.now() + delta
                    queued_task.save()

                return

            logger.error("No more retries for finally failed %s: %s", dicom_task, str(err))

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
        except ValueError as err:
            # We raise ValueError for expected errors
            logger.exception("Error during %s.", dicom_task)

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
            if dicom_task.log:
                dicom_task.log += "\n---\n"
            dicom_task.log += traceback.format_exc()
        except Exception as err:
            # Unexpected errors are handled here
            logger.exception("Unexpected error during %s.", dicom_task)

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
            if dicom_task.log:
                dicom_task.log += "\n-----\n"
            dicom_task.log += traceback.format_exc()
        finally:
            dicom_task.end = timezone.now()

            # Django ORM does not work well with long running tasks in production as the
            # database server closes the connection, but Django still tries to use the closed
            # connection and then throws an error. We just try again then which hopefully
            # and just creates new connection.
            # An alternative would be to use db.close_old_connections(), but that breaks our
            # tests as it also closes some pytest connections.
            # References:
            # <https://code.djangoproject.com/ticket/24810>
            # <https://github.com/jdelic/django-dbconn-retry> No support for psycopg v3
            # <https://tryolabs.com/blog/2014/02/12/long-running-process-and-django-orm>
            # <https://docs.djangoproject.com/en/4.2/ref/databases/#caveats>
            try:
                dicom_task.save()
            except db.OperationalError:
                dicom_task.save()

            logger.info("%s ended.", dicom_task)

            dicom_job = dicom_task.job

            with self._redis.lock("update_job_after_task"):
                dicom_job.refresh_from_db()
                job_finished = update_job_status(dicom_job)
                dicom_job.end = timezone.now()
                dicom_job.save()

            if job_finished and dicom_job.send_finished_mail:
                send_job_finished_mail(dicom_job)

            logger.info("%s ended.", dicom_job)

    def process_dicom_task(
        self, dicom_task: DicomTask
    ) -> tuple[DicomTask.Status, str, list[DicomLogEntry]]:
        dicom_job = dicom_task.job

        # Dicom jobs are canceled by the DicomJobCancelView and tasks are also revoked there,
        # but it could happen that the task was already picked up by a worker or under rare
        # circumstances will nevertheless get picked up by a worker (e.g. the worker crashes
        # and forgot its revoked tasks). We then just ignore that task.
        if (
            dicom_task.status == DicomTask.Status.CANCELED
            or dicom_job.status == DicomJob.Status.CANCELED
            or dicom_job.status == DicomJob.Status.CANCELING
        ):
            logger.debug(f"{dicom_task} cancelled.")
            return (DicomTask.Status.CANCELED, "Task was canceled.", [])

        if dicom_task.status != dicom_task.Status.PENDING:
            raise AssertionError(f"Invalid {dicom_task} status: {dicom_task.get_status_display()}")

        logger.info("%s started.", dicom_task)

        # When the first DICOM task is really processed then the status of the DICOM
        # job switches from PENDING to IN_PROGRESS
        # TODO: Maybe it would be nicer if the job is only IN_PROGRESS as long as a
        # DICOM task is currently IN_PROGRESS (cave, must be handled in a distributed lock)
        if dicom_job.status == DicomJob.Status.PENDING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
            dicom_job.start = timezone.now()
            dicom_job.save()

        dicom_task.status = DicomTask.Status.IN_PROGRESS
        dicom_task.start = timezone.now()
        dicom_task.save()

        return self.handle_dicom_task(dicom_task)

    def handle_dicom_task(self, dicom_task) -> tuple[DicomTask.Status, str, list[DicomLogEntry]]:
        """Does the actual work of the dicom task.

        Should return a tuple of the final status of that task and a message that is
        stored in the task model.
        """
        raise NotImplementedError("Subclasses must implement this method.")
