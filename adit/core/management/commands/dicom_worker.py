from datetime import time

from adit.core.utils.command_utils import valid_time_range
from adit.core.workers import DicomWorker

from ..base.server_command import ServerCommand


class Command(ServerCommand):
    help = "Starts a DICOM worker"
    server_name = "DICOM Worker"
    _dicom_worker: DicomWorker | None

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
            help="The time slot in which the worker should process tasks, e.g. 20:00-05:00.",
        )

    def run_server(self, **options):
        time_slot: tuple[time, time] | None = options["time_slot"]
        polling_interval: int = options["polling_interval"]

        self._dicom_worker = DicomWorker(polling_interval, time_slot)
        self._dicom_worker.run()

    def on_shutdown(self):
        if self._dicom_worker:
            self._dicom_worker.shutdown()
