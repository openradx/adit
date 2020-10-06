from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def continuous_transfer(job_id):
    logger.info("Prepare continuous transfer job (Job ID %d).", job_id)
