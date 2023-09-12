import logging
import shlex
import socket
import subprocess

from ..base.server_command import ServerCommand

logger = logging.getLogger(__name__)


class Command(ServerCommand):
    help = "Starts a Celery worker"
    server_name = "Celery worker"
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
            default=1,
            help="Number of child processes processing the queue.",
        )

    def run_server(self, **options):
        queue = options["queue"]
        loglevel = options["loglevel"]
        concurrency = options["concurrency"]
        hostname = f"worker_{queue}_{socket.gethostname()}"
        cmd = f"celery -A adit worker -Q {queue} -l {loglevel} -c {concurrency} -n {hostname}"

        self.worker_process = subprocess.Popen(shlex.split(cmd))
        self.worker_process.wait()

    def on_shutdown(self):
        assert self.worker_process
        self.worker_process.terminate()
