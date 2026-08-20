import logging

from django.core.management.base import BaseCommand

from adit.core.utils.recovery import sweep_stale_dicom_tasks

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Repair DICOM tasks left IN_PROGRESS by a killed worker."

    def handle(self, *args, **options):
        self.stdout.write("Sweeping stale dicom tasks... ", ending="")
        self.stdout.flush()

        # Runs before bg_worker in the container start command (chained with &&), so it
        # must never fail: the worker must start even if the sweep breaks.
        try:
            sweep_stale_dicom_tasks()
        except Exception:
            logger.exception("Sweeping stale dicom tasks failed.")
            self.stdout.write("failed (see logs)")
        else:
            self.stdout.write("done")
