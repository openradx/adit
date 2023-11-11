import argparse
import logging
from datetime import time
from threading import Event
from typing import cast

import redis
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from adit.core.models import DicomTask, QueuedTask
from adit.core.site import dicom_processors

from ..base.server_command import ServerCommand

logger = logging.getLogger(__name__)

LOCK = "next_queued_task"


def valid_time_range(value: str) -> tuple[time, time] | None:
    if not value:
        return None

    try:
        start, end = value.split("-")
        return (
            time.fromisoformat(start),
            time.fromisoformat(end),
        )
    except ValueError:
        raise argparse.ArgumentTypeError("Invalid time range.")


def in_time_slot(start_time: time, end_time: time, check_time: time) -> bool:
    """Checks if the current time is in a time range."""
    if start_time < end_time:
        return check_time >= start_time and check_time <= end_time
    else:  # crosses midnight
        return check_time >= start_time or check_time <= end_time


class Command(ServerCommand):
    help = "Starts a DICOM worker"
    server_name = "DICOM Worker"
    current_queued_task: QueuedTask | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Redis for distributed locking
        self._redis = redis.Redis.from_url(settings.REDIS_URL)

        self._stop = Event()

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "-p",
            "--polling-interval",
            type=int,
            default=5,
            help="The polling interval to check for new queued tasks.",
        )
        parser.add_argument(
            "-t",
            "--time-slot",
            type=valid_time_range,
            default=None,
            help="The time slot in which the worker should process tasks.",
        )

    def run_server(self, **options):
        while True:
            if self._stop.is_set():
                break

            if options["time_slot"]:
                slot: tuple[time, time] = options["time_slot"]
                if not in_time_slot(slot[0], slot[1], timezone.now().time()):
                    self._stop.wait(options["polling_interval"])
                    continue

            with self._redis.lock(LOCK):
                queued_task = self.get_next_queued_task()

            if not queued_task:
                self._stop.wait(options["polling_interval"])
                continue

            logger.debug(f"Next queued task being processed: {queued_task}")

            self.current_queued_task = queued_task
            dicom_task = cast(DicomTask, queued_task.content_object)
            model_label = f"{dicom_task._meta.app_label}.{dicom_task._meta.model_name}"
            Processor = dicom_processors[model_label]
            if not Processor:
                raise AssertionError(f"No processor found for {model_label}.")

            try:
                processor = Processor()
                processor.run(queued_task)
                queued_task.delete()
            except Exception:
                logger.exception(f"DICOM worker failed to process queued task {queued_task}.")
            finally:
                self.current_queued_task = None

    def get_next_queued_task(self) -> QueuedTask | None:
        queued_tasks = QueuedTask.objects.filter(Q(eta=None) | Q(eta__lt=timezone.now()))
        queued_tasks = queued_tasks.order_by("-priority")
        queued_tasks = queued_tasks.order_by("created")
        return queued_tasks.first()

    def on_shutdown(self):
        self._stop.set()
        lock = self._redis.lock(LOCK)
        if lock.locked():
            lock.release()

        # TODO: Somehow handle an already current_queued_task
        # Maybe run processor in another process that can be killed and reset
        # the dicom task to pending or set it to failure with some message that
        # the server was killed in between
