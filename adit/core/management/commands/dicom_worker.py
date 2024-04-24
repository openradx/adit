from datetime import time

from adit_radis_shared.common.management.base.server_command import ServerCommand
from django.conf import settings

from adit.core.utils.time_utils import valid_time_range
from adit.core.workers import DicomWorker


class Command(ServerCommand):
    help = "Starts a DICOM worker"
    server_name = "DICOM Worker"
    paths_to_watch = [settings.BASE_DIR / "adit"]
    _dicom_worker: DicomWorker | None

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "-p",
            "--polling-interval",
            type=int,
            default=5,
            help="The interval (in seconds) to check for new queued tasks.",
        )
        parser.add_argument(
            "-m",
            "--monitor-interval",
            type=int,
            default=5,
            help="The interval (in seconds) to check if the task process should be killed.",
        )
        parser.add_argument(
            "-t",
            "--time-slot",
            type=valid_time_range,
            default=None,
            help="The time slot in which the worker should process tasks, e.g. 20:00-05:00.",
        )

    def run_server(self, **options):
        polling_interval: int = options["polling_interval"]
        monitor_interval: int = options["monitor_interval"]
        time_slot: tuple[time, time] | None = options["time_slot"]

        self._dicom_worker = DicomWorker(polling_interval, monitor_interval, time_slot)
        self._dicom_worker.run()

    def on_shutdown(self):
        # TODO: We must somehow force it to shutdown after some time period
        if self._dicom_worker:
            self._dicom_worker.shutdown()
