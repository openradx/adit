from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from adit.core.utils import task_utils
from .models import StudyFinderJob, StudyFinderQuery, StudyFinderSettings

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def find_studies(job_id):
    logger.info("Prepare study finder job. [Job ID %d]", job_id)

    job = StudyFinderJob.objects.get(id=job_id)

    task_utils.precheck_job(job)

    priority = settings.STUDY_TRANSFER_DEFAULT_PRIORITY
    if job.urgent:
        priority = settings.STUDY_TRANSFER_URGENT_PRIORITY

    process_queries = [
        process_query.s(query.id).set(priority=priority) for query in job.queries.all()
    ]

    chord(process_queries)(
        on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id))
    )


@shared_task(bind=True)
def process_query(self, query_id):
    query = StudyFinderQuery.objects.get(id=query_id)
    job = query.job

    logger.info("Processing %s.", query)

    task_utils.precheck_task(query)

    canceled_status = task_utils.check_canceled(job, query)
    if canceled_status:
        return canceled_status

    task_utils.check_can_run_now(self, StudyFinderSettings.get(), job, query)


@shared_task
def on_job_finished(query_status_list, job_id):
    pass


# The Celery documentation is wrong about the provided parameters and when
# the callback is called. This function definition seems to work however.
# See https://github.com/celery/celery/issues/3709
@shared_task
def on_job_failed(*args, **kwargs):
    pass
