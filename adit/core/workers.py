import logging
import traceback
from datetime import time, timedelta
from threading import Event
from typing import Literal, cast

import humanize
import redis
from django import db
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from adit.core.errors import DicomConnectionError, OutOfDiskSpaceError
from adit.core.models import DicomJob, DicomTask, QueuedTask
from adit.core.processors import ProcessDicomTask
from adit.core.site import dicom_processors
from adit.core.utils.job_utils import update_job_status
from adit.core.utils.mail import send_job_finished_mail

from .utils.worker_utils import in_time_slot

logger = logging.getLogger(__name__)

TimeSlot = tuple[time, time]

DISTRIBUTED_LOCK = "dicom_worker_lock"
MAX_PRIORITY = 10


class DicomWorker:
    def __init__(self, polling_interval: int = 5, time_slot: TimeSlot | None = None) -> None:
        self._polling_interval = polling_interval
        self._time_slot = time_slot

        self._redis = redis.Redis.from_url(settings.REDIS_URL)
        self._stop = Event()

    def run(self) -> None:
        while True:
            if self._stop.is_set():
                break

            if self._time_slot and not in_time_slot(
                self._time_slot[0], self._time_slot[1], timezone.now().time()
            ):
                self._stop.wait(self._polling_interval)
                continue

            if not self.process_next_task():
                self._stop.wait(self._polling_interval)
                continue

    def process_next_task(self) -> bool:
        dicom_task: DicomTask | None = None
        processor: ProcessDicomTask | None = None
        with self._redis.lock(DISTRIBUTED_LOCK):
            queued_task = self.fetch_next_queued_task()
            if not queued_task:
                return False

            logger.debug(f"Next queued task being processed: {queued_task}")
            prep_result = self.prepare_processing(queued_task)
            if not prep_result:
                return True

            dicom_task, processor = prep_result
            logger.info(f"{dicom_task} started.")

        try:
            status, message, logs = processor.process_dicom_task(dicom_task)
            dicom_task.status = status
            dicom_task.message = message
            dicom_task.log = "\n".join([log["message"] for log in logs])
            queued_task.delete()
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
                queued_task.locked = False
                queued_task.save()
            else:
                logger.error("No more retries for finally failed %s: %s", dicom_task, str(err))

                dicom_task.status = DicomTask.Status.FAILURE
                dicom_task.message = str(err)
                queued_task.delete()
        except ValueError as err:
            # We raise ValueError for expected errors
            logger.exception("Error during %s.", dicom_task)

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
            if dicom_task.log:
                dicom_task.log += "\n---\n"
            dicom_task.log += traceback.format_exc()
            queued_task.delete()
        except Exception as err:
            # Unexpected errors are handled here
            logger.exception("Unexpected error during %s.", dicom_task)

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
            if dicom_task.log:
                dicom_task.log += "\n-----\n"
            dicom_task.log += traceback.format_exc()
            queued_task.delete()
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

            logger.info(f"{dicom_task} ended.")

            dicom_job = dicom_task.job

            with self._redis.lock(DISTRIBUTED_LOCK):
                dicom_job.refresh_from_db()
                job_finished = update_job_status(dicom_job)
                dicom_job.end = timezone.now()
                dicom_job.save()

            if job_finished:
                logger.info(f"{dicom_job} ended.")

                if dicom_job.send_finished_mail:
                    send_job_finished_mail(dicom_job)

            return True

    def fetch_next_queued_task(self) -> QueuedTask | None:
        queued_tasks = QueuedTask.objects.filter(locked=False)
        queued_tasks = queued_tasks.filter(Q(eta=None) | Q(eta__lt=timezone.now()))
        queued_tasks = queued_tasks.order_by("-priority")
        queued_tasks = queued_tasks.order_by("created")
        return queued_tasks.first()

    def prepare_processing(
        self, queued_task: QueuedTask
    ) -> tuple[DicomTask, ProcessDicomTask] | Literal[False]:
        # We have to lock this queued task so that no other worker can pick it up
        queued_task.locked = True
        queued_task.save()

        dicom_task = cast(DicomTask, queued_task.content_object)
        processor = self.get_processor(dicom_task)

        if processor.is_suspended():
            delta = timedelta(minutes=60)
            queued_task.eta = timezone.now() + delta
            queued_task.locked = False
            queued_task.save()
            logger.info(
                f"{processor.app_name} suspended. "
                "Rescheduling {dicom_task} in {humanize.naturaldelta(delta)}."
            )
            return False

        assert dicom_task.status == dicom_task.Status.PENDING

        # When the first DICOM task is really processed then the status of the DICOM
        # job switches from PENDING to IN_PROGRESS
        # TODO: Maybe it would be nicer if the job is only IN_PROGRESS as long as a
        # DICOM task is currently IN_PROGRESS (cave, must be handled in a distributed lock)
        dicom_job = dicom_task.job
        if dicom_job.status == DicomJob.Status.PENDING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
            dicom_job.start = timezone.now()
            dicom_job.save()

        dicom_task.status = DicomTask.Status.IN_PROGRESS
        dicom_task.start = timezone.now()
        dicom_task.save()

        return (dicom_task, processor)

    def get_processor(self, dicom_task: DicomTask) -> ProcessDicomTask:
        model_label = f"{dicom_task._meta.app_label}.{dicom_task._meta.model_name}"
        Processor = dicom_processors[model_label]
        assert Processor is not None
        return Processor()

    def shutdown(self) -> None:
        self._stop.set()
        lock = self._redis.lock(DISTRIBUTED_LOCK)
        if lock.locked():
            lock.release()
        self._redis.close()

        # TODO: Somehow handle an task that is in the middle of being processed
        # Maybe run processor in another process that can be killed and reset
        # the dicom task to pending or set it to failure with some message that
        # the server was killed in between
