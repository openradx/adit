import logging
import traceback
from concurrent import futures
from datetime import time, timedelta
from threading import Event
from time import sleep
from typing import cast

import humanize
import redis
from django import db
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from pebble import ProcessFuture, concurrent

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomJob, DicomTask, QueuedTask
from adit.core.processors import DicomTaskProcessor
from adit.core.site import dicom_processors
from adit.core.types import ProcessingResult
from adit.core.utils.db_utils import ensure_db_connection
from adit.core.utils.job_utils import update_job_status
from adit.core.utils.mail import send_job_finished_mail

from .utils.worker_utils import in_time_slot

logger = logging.getLogger(__name__)

TimeSlot = tuple[time, time]

DISTRIBUTED_LOCK = "dicom_worker_lock"
PROCESS_TIMEOUT = 60 * 20  # 20 minutes
MAX_PRIORITY = 10


class DicomWorker:
    def __init__(
        self,
        polling_interval: float = 5,
        monitor_interval: float = 5,
        time_slot: TimeSlot | None = None,
    ) -> None:
        self._polling_interval = polling_interval
        self._monitor_interval = monitor_interval
        self._time_slot = time_slot

        self._redis = redis.Redis.from_url(settings.REDIS_URL)
        self._stop_worker = Event()
        self._process: ProcessFuture | None = None

    def run(self) -> None:
        while True:
            if self._stop_worker.is_set():
                break

            if self._time_slot and not in_time_slot(
                self._time_slot[0], self._time_slot[1], timezone.now().time()
            ):
                self._stop_worker.wait(self._polling_interval)
                continue

            if not self.check_and_process_next_task():
                self._stop_worker.wait(self._polling_interval)
                continue

    def check_and_process_next_task(self) -> bool:
        """Check for a queued task and process it if found.

        Returns: True if a task was processed, False otherwise
        """
        queued_task = self._fetch_queued_task()
        if not queued_task:
            return False

        dicom_task = cast(DicomTask, queued_task.content_object)
        assert dicom_task.status == dicom_task.Status.PENDING

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
        dicom_task.save()

        logger.info(f"Processing of {dicom_task} started.")

        try:
            self._process = cast(ProcessFuture, self._process_dicom_task(queued_task.id))
            self._monitor_task(queued_task.id, self._process)
            result: ProcessingResult = self._process.result()
            dicom_task.status = result["status"]
            dicom_task.message = result["message"]
            dicom_task.log = result["log"]

            ensure_db_connection()
            queued_task.delete()
        except futures.TimeoutError:
            dicom_task.message = "Task was aborted due to timeout."
            dicom_task.status = DicomTask.Status.FAILURE

            ensure_db_connection()
            queued_task.delete()
        except futures.CancelledError:
            dicom_task.status = DicomTask.Status.FAILURE
            if self._stop_worker.is_set():
                dicom_task.message = "Task was aborted by worker shutdown."
            else:
                dicom_task.message = "Task was killed by admin."

            ensure_db_connection()
            queued_task.delete()
        except RetriableDicomError as err:
            logger.exception("Retriable error occurred during %s.", dicom_task)

            if dicom_task.retries < settings.DICOM_TASK_RETRIES:
                delta = err.delta
                humanized_delta = humanize.naturaldelta(delta)

                logger.info(f"Retrying {dicom_task} in {humanized_delta}.")

                dicom_task.status = DicomTask.Status.PENDING
                dicom_task.message = f"Task failed, but will be retried in {humanized_delta}."
                if dicom_task.log:
                    dicom_task.log += "\n"
                dicom_task.log += str(err)

                dicom_task.retries += 1

                # Increase the priority slightly to make sure the task will be retried soon
                priority = queued_task.priority
                if priority < MAX_PRIORITY:
                    queued_task.priority = priority + 1

                ensure_db_connection()
                queued_task.eta = timezone.now() + delta
                queued_task.save()
            else:
                logger.error("No more retries for finally failed %s: %s", dicom_task, str(err))

                dicom_task.status = DicomTask.Status.FAILURE
                dicom_task.message = str(err)

                ensure_db_connection()
                queued_task.delete()
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
            queued_task.delete()
        finally:
            self._process = None

            dicom_task.end = timezone.now()
            dicom_task.save()
            logger.info(f"Processing of {dicom_task} ended.")

            with self._redis.lock(DISTRIBUTED_LOCK):
                dicom_job.refresh_from_db()
                job_finished = update_job_status(dicom_job)

            if job_finished:
                logger.info(f"Processing of {dicom_job} ended.")

                if dicom_job.send_finished_mail:
                    send_job_finished_mail(dicom_job)

            # Unlock the queued task. The queued task may also be already deleted
            # when everything worked well.
            try:
                queued_task.refresh_from_db()
                queued_task.locked = False
                queued_task.save()
            except QueuedTask.DoesNotExist:
                pass

        return True

    def _fetch_queued_task(self) -> QueuedTask | None:
        with self._redis.lock(DISTRIBUTED_LOCK):
            queued_tasks = QueuedTask.objects.filter(locked=False)
            queued_tasks = queued_tasks.filter(Q(eta=None) | Q(eta__lt=timezone.now()))
            queued_tasks = queued_tasks.order_by("-priority")
            queued_tasks = queued_tasks.order_by("created")
            queued_task = queued_tasks.first()

            if not queued_task:
                return None

            dicom_task = cast(DicomTask, queued_task.content_object)
            processor = self._get_processor(dicom_task)

            if processor.is_suspended():
                delta = timedelta(minutes=60)
                queued_task.eta = timezone.now() + delta
                queued_task.save()
                logger.info(
                    f"{processor.app_name} suspended. "
                    "Rescheduling {dicom_task} in {humanize.naturaldelta(delta)}."
                )
                return None

            # We have to lock this queued task so that no other worker can pick it up
            queued_task.locked = True
            queued_task.save()

        logger.debug(f"Next queued task being processed: {queued_task}")
        return queued_task

    # Pebble allows us to set a timeout and terminates the process if it takes too long
    @concurrent.process(timeout=10, daemon=True)
    def _process_dicom_task(self, queued_task_id: int) -> ProcessingResult:
        queued_task = QueuedTask.objects.get(id=queued_task_id)
        dicom_task = cast(DicomTask, queued_task.content_object)
        processor = self._get_processor(dicom_task)

        logger.info(f"Processing {dicom_task} started.")

        return processor.process_dicom_task(dicom_task)

    def _get_processor(self, dicom_task: DicomTask) -> DicomTaskProcessor:
        model_label = f"{dicom_task._meta.app_label}.{dicom_task._meta.model_name}"
        Processor = dicom_processors[model_label]
        assert Processor is not None
        return Processor()

    @concurrent.thread
    def _monitor_task(self, queued_task_id: int, process_future: ProcessFuture) -> None:
        while not process_future.done():
            queued_task = QueuedTask.objects.get(pk=queued_task_id)
            if queued_task.kill:
                process_future.cancel()
                sleep(self._monitor_interval)
        db.close_old_connections()

    def shutdown(self) -> None:
        logger.info("Shutting down DICOM worker...")

        with self._redis.lock(DISTRIBUTED_LOCK):
            self._stop_worker.set()

        if self._process:
            self._process.cancel()

        self._redis.close()
