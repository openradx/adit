import shlex
import subprocess
import logging
from pathlib import Path
from functools import partial
from django.core.management.base import BaseCommand
from django.utils import autoreload

logger = logging.getLogger(__name__)


def restart_celery_beat(options):
    cmd = "pkill celery"
    subprocess.call(shlex.split(cmd))

    folder_path = Path("/var/www/adit/celery/")
    folder_path.mkdir(parents=True, exist_ok=True)
    schedule_path = folder_path / "celerybeat-schedule"
    pid_path = folder_path / "celerybeat.pid"
    loglevel = options["loglevel"]
    cmd = f"celery -A adit beat -l {loglevel} -s {str(schedule_path)} --pidfile {str(pid_path)}"
    logger.info("Starting celery beat with '%s'.", cmd)
    subprocess.call(shlex.split(cmd))


class Command(BaseCommand):
    help = "Starts a Celery worker"

    def add_arguments(self, parser):
        # Adapted form https://docs.celeryproject.org/en/stable/reference/cli.html
        parser.add_argument(
            "-l",
            "--loglevel",
            default="INFO",
            help="Logging level.",
        )
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Autoreload the celery worker.",
        )

    def handle(self, *args, **options):
        if options["autoreload"]:
            logger.info("Starting celery beat with autoreload...")
            autoreload.run_with_reloader(partial(restart_celery_beat, options))
        else:
            restart_celery_beat(options)
