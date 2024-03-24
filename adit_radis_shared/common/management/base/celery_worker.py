import logging
import shlex
import socket
import subprocess
from typing import Literal

from django.conf import settings

from .server_command import ServerCommand

logger = logging.getLogger(__name__)


class CeleryWorkerCommand(ServerCommand):
    project: Literal["adit", "radis"]
    help = "Starts a Celery worker"
    server_name = "Celery worker"
    paths_to_watch = [settings.BASE_DIR / "adit"]
    worker_process: subprocess.Popen | None

    def __init__(self, *args, **kwargs):
        self.worker_process = None
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super().add_arguments(parser)

        # https://docs.celeryproject.org/en/stable/reference/cli.html
        parser.add_argument(
            "-Q",
            "--queue",
            required=True,
            help="The celery queue.",
        )
        parser.add_argument(
            "-l",
            "--loglevel",
            default="INFO",
            help="Logging level.",
        )
        parser.add_argument(
            "-c",
            "--concurrency",
            type=int,
            default=0,
            help="Number of child processes processing the queue (defaults to number of CPUs).",
        )

    def run_server(self, **options):
        queue = options["queue"]
        loglevel = options["loglevel"]
        hostname = f"worker_{queue}_{socket.gethostname()}"

        cmd = f"celery -A {self.project} worker -Q {queue} -l {loglevel} -n {hostname}"

        concurrency = options["concurrency"]
        if concurrency >= 1:
            cmd += f" -c {concurrency}"

        self.worker_process = subprocess.Popen(shlex.split(cmd))
        self.worker_process.wait()

    def on_shutdown(self):
        assert self.worker_process
        self.worker_process.terminate()
        self.worker_process.wait()
