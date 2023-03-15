import logging
import shlex
import socket
import subprocess
from datetime import datetime

from ..base.server_command import ServerCommand

logger = logging.getLogger(__name__)


class Command(ServerCommand):
    help = "Starts a Celery worker"

    starting_message = True

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
        # Kill previous running worker
        logger.debug("Killing Celery worker.")
        cmd = "pkill celery"
        subprocess.call(shlex.split(cmd))

        # Start a new worker
        queue = options["queue"]
        loglevel = options["loglevel"]
        concurrency = options["concurrency"]
        hostname = f"worker_{queue}_{socket.gethostname()}"
        cmd = f"celery -A adit worker -Q {queue} -l {loglevel} -c {concurrency} -n {hostname}"

        now = datetime.now().strftime("%B %d, %Y - %X")
        self.stdout.write(now)
        self.stdout.write(
            ("Starting Celery worker with command:\n" "%(cmd)s\n" "Quit with %(quit_command)s.")
            % {
                "cmd": cmd,
                "quit_command": self.quit_command,
            }
        )

        self.worker_process = subprocess.Popen(shlex.split(cmd))
        self.worker_process.wait()

    def on_shutdown(self):
        self.worker_process.terminate()
