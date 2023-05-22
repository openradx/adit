import logging
import shlex
import subprocess
from pathlib import Path

from ..base.server_command import ServerCommand

logger = logging.getLogger(__name__)


class Command(ServerCommand):
    help = "Starts Celery beat scheduler"
    server_name = "Celery beat scheduler"

    def __init__(self, *args, **kwargs):
        self.beat_process = None
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super().add_arguments(parser)

        # https://docs.celeryproject.org/en/stable/reference/cli.html
        parser.add_argument(
            "-l",
            "--loglevel",
            default="INFO",
            help="Logging level.",
        )

    def run_server(self, **options):
        # Kill previous running beat
        logger.debug("Killing Celery beat.")
        cmd = "pkill celery"
        subprocess.call(shlex.split(cmd))

        # Start new Celery beat
        folder_path = Path("/var/www/adit/celery/")
        folder_path.mkdir(parents=True, exist_ok=True)
        schedule_path = folder_path / "celerybeat-schedule"
        loglevel = options["loglevel"]

        # --pidfile= disables pidfile creation as we can control the process with subprocess
        cmd = f"celery -A adit beat -l {loglevel} -s {str(schedule_path)} --pidfile="

        self.beat_process = subprocess.Popen(shlex.split(cmd))
        self.beat_process.wait()

    def on_shutdown(self):
        self.beat_process.terminate()
