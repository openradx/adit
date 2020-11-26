import shlex
import subprocess
import logging
import socket
from functools import partial
from django.core.management.base import BaseCommand
from django.utils import autoreload

logger = logging.getLogger(__name__)


def restart_celery_worker(options):
    cmd = "pkill celery"
    subprocess.call(shlex.split(cmd))

    queue = options["queue"]
    loglevel = options["loglevel"]
    concurrency = options["concurrency"]
    hostname = f"worker_{queue}_{socket.gethostname()}"
    cmd = (
        f"celery -A adit worker -Q {queue} -l {loglevel} -c {concurrency} -n {hostname}"
    )
    logger.info("Starting celery worker with '%s'.", cmd)
    subprocess.call(shlex.split(cmd))


class Command(BaseCommand):
    help = "Starts a Celery worker"

    def add_arguments(self, parser):
        # Adapted form https://docs.celeryproject.org/en/stable/reference/cli.html
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
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Autoreload the celery worker.",
        )

    def handle(self, *args, **options):
        if options["autoreload"]:
            logger.info("Starting celery worker with autoreload...")
            autoreload.run_with_reloader(partial(restart_celery_worker, options))
        else:
            restart_celery_worker(options)
