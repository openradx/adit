import logging

from django.conf import settings
from procrastinate import JobContext
from procrastinate.contrib.django import app

from adit.core.tasks import DICOM_TASK_RETRY_STRATEGY, _run_dicom_task

logger = logging.getLogger(__name__)


@app.task(queue="dicom", pass_context=True, retry=DICOM_TASK_RETRY_STRATEGY)
def process_router_task(context: JobContext, model_label: str, task_id: int):
    _run_dicom_task(context, model_label, task_id, process_timeout=settings.ROUTER_PROCESS_TIMEOUT)
