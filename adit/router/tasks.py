import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from procrastinate import JobContext
from procrastinate.contrib.django import app

from adit.core.tasks import DICOM_TASK_RETRY_STRATEGY, _run_dicom_task

from .utils.closer import clear_old_sent_lists, report_failed_deliveries, run_spool_cycle

logger = logging.getLogger(__name__)


@app.task(queue="dicom", pass_context=True, retry=DICOM_TASK_RETRY_STRATEGY)
def process_router_task(context: JobContext, model_label: str, task_id: int):
    _run_dicom_task(context, model_label, task_id, process_timeout=settings.ROUTER_PROCESS_TIMEOUT)


@app.periodic(cron=settings.ROUTER_CLOSE_CRON)
@app.task(queue="default", queueing_lock="close_router_batches", lock="close_router_batches")
def close_router_batches(timestamp: int) -> None:
    spool_root = Path(settings.ROUTER_SPOOL_PATH)
    # Workers without the spool mounted, like the web container's test workers, skip.
    if not spool_root.is_dir():
        logger.warning("The router spool %s is not mounted here; skipping.", spool_root)
        return
    run_spool_cycle(spool_root, timezone.now())


@app.periodic(cron="0 7 * * *")  # every day at 7am
@app.task(queue="default", queueing_lock="report_router_failures")
def report_router_failures(timestamp: int) -> None:
    now = timezone.now()
    report_failed_deliveries(now)
    clear_old_sent_lists(now)
