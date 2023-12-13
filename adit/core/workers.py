import logging
import traceback
from concurrent.futures import CancelledError, TimeoutError
from datetime import time, timedelta
from threading import Event
from typing import cast

import humanize
import redis
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from pebble import ProcessFuture, concurrent

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomJob, DicomTask, QueuedTask
from adit.core.processors import DicomTaskProcessor
from adit.core.site import dicom_processors
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
    def __init__(self, polling_interval: int = 5, time_slot: TimeSlot | None = None) -> None:
        self._polling_interval = polling_interval
        self._time_slot = time_slot

        self._redis = redis.Redis.from_url(settings.REDIS_URL)
        self._stop = Event()
        self._future: ProcessFuture | None = None

    def run(self) -> None:
        while True:
            if self._stop.is_set():
                break

            if self._time_slot and not in_time_slot(
                self._time_slot[0], self._time_slot[1], timezone.now().time()
            ):
                self._stop.wait(self._polling_interval)
                continue

            if not self.check_and_process_next_task():
                self._stop.wait(self._polling_interval)
                continue

    def check_and_process_next_task(self) -> bool:
        queued_task = self._fetch_queued_task()
        if not queued_task:
            return False

        try:
            self._future = cast(ProcessFuture, self._process_dicom_task(queued_task.id))
            self._future.result()
        except TimeoutError:
            dicom_task = cast(DicomTask, queued_task.content_object)
            dicom_task.message = "Task was aborted due to timeout."
            dicom_task.status = DicomTask.Status.FAILURE
        except CancelledError:
            # TODO: check that this really works
            dicom_task = cast(DicomTask, queued_task.content_object)
            dicom_task.message = "Task was aborted cause of worker shutdown."
            dicom_task.status = DicomTask.Status.FAILURE
        finally:
            self._future = None

            ensure_db_connection()

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
    @concurrent.process(timeout=PROCESS_TIMEOUT, daemon=True)
    def _process_dicom_task(self, queued_task_id: int) -> None:
        queued_task = QueuedTask.objects.get(id=queued_task_id)
        dicom_task = cast(DicomTask, queued_task.content_object)
        processor = self._get_processor(dicom_task)

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

            logger.info(f"Processing {dicom_job} started.")

        dicom_task.status = DicomTask.Status.IN_PROGRESS
        dicom_task.start = timezone.now()
        dicom_task.save()

        logger.info(f"Processing {dicom_task} started.")

        try:
            status, message, logs = processor.process_dicom_task(dicom_task)
            dicom_task.status = status
            dicom_task.message = message
            dicom_task.log = "\n".join([log["message"] for log in logs])
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

                queued_task.eta = timezone.now() + delta
                queued_task.save()
            else:
                logger.error("No more retries for finally failed %s: %s", dicom_task, str(err))

                dicom_task.status = DicomTask.Status.FAILURE
                dicom_task.message = str(err)
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
            queued_task.delete()
        finally:
            dicom_task.end = timezone.now()

            ensure_db_connection()

            dicom_task.save()

            logger.info(f"Processing {dicom_task} ended.")

            dicom_job = dicom_task.job

            with self._redis.lock(DISTRIBUTED_LOCK):
                dicom_job.refresh_from_db()
                job_finished = update_job_status(dicom_job)
                dicom_job.end = timezone.now()
                dicom_job.save()

            if job_finished:
                logger.info(f"Processing {dicom_job} ended.")

                if dicom_job.send_finished_mail:
                    send_job_finished_mail(dicom_job)

    def _get_processor(self, dicom_task: DicomTask) -> DicomTaskProcessor:
        model_label = f"{dicom_task._meta.app_label}.{dicom_task._meta.model_name}"
        Processor = dicom_processors[model_label]
        assert Processor is not None
        return Processor()

    def shutdown(self) -> None:
        logger.info("Shutting down DICOM worker...")

        with self._redis.lock(DISTRIBUTED_LOCK):
            self._stop.set()

        if self._future:
            self._future.cancel()

        self._redis.close()
