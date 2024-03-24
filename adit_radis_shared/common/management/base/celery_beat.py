import logging
import shlex
import subprocess
from pathlib import Path
from typing import Literal

from django.conf import settings

from .server_command import ServerCommand

logger = logging.getLogger(__name__)


class CeleryBeatCommand(ServerCommand):
    project: Literal["adit", "radis"]
    help = "Starts Celery beat scheduler"
    server_name = "Celery beat scheduler"
    paths_to_watch = [settings.BASE_DIR / "adit"]

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
        folder_path = Path(f"/var/www/{self.project}/celery/")
        folder_path.mkdir(parents=True, exist_ok=True)
        schedule_path = folder_path / "celerybeat-schedule"
        loglevel = options["loglevel"]

        # --pidfile= disables pidfile creation as we can control the process with subprocess
        cmd = f"celery -A {self.project} beat -l {loglevel} -s {str(schedule_path)} --pidfile="

        self.beat_process = subprocess.Popen(shlex.split(cmd))
        self.beat_process.wait()

    def on_shutdown(self):
        assert self.beat_process
        self.beat_process.terminate()
        self.beat_process.wait()
