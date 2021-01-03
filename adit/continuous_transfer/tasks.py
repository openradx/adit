from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from .models import ContinuousTransferJob

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def process_transfer_job(transfer_job_id: int):
    job = ContinuousTransferJob.objects.get(id=transfer_job_id)

    priority = settings.CONTINUOUS_TRANSFER_DEFAULT_PRIORITY
    if job.urgent:
        priority = settings.CONTINUOUS_TRANSFER_URGENT_PRIORITY


@shared_task
def transfer_next_dicoms(task_id):
    raise NotImplementedError("Transfer continuous task must be implemented.")
