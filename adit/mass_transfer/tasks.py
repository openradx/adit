import logging

from procrastinate import JobContext, RetryStrategy
from procrastinate.contrib.django import app

from adit.core.models import DicomJob, DicomTask
from adit.core.tasks import DICOM_TASK_RETRY_STRATEGY, _run_dicom_task
from adit.core.utils.model_utils import get_model_label

logger = logging.getLogger(__name__)


# Separate task function for mass transfer on a dedicated queue so it does not
# starve batch/selective transfers.  Mass transfer tasks process an entire
# partition (discovery + export + convert) and can run for hours, so the
# pebble process timeout is disabled (process_timeout=None).  Individual DICOM
# operations are still protected by Stamina / pynetdicom-level timeouts.
@app.task(
    queue="mass_transfer",
    pass_context=True,
    retry=DICOM_TASK_RETRY_STRATEGY,
)
def process_mass_transfer_task(context: JobContext, model_label: str, task_id: int):
    _run_dicom_task(context, model_label, task_id, process_timeout=None)


@app.task(queue="default", retry=RetryStrategy(max_attempts=3, wait=10))
def queue_mass_transfer_tasks(job_id: int):
    """Queues all pending tasks for a mass transfer job.

    Runs on the default worker so that the HTTP view returns immediately
    instead of blocking on thousands of individual defer() calls.
    """
    from .models import MassTransferJob

    try:
        job = MassTransferJob.objects.get(pk=job_id)
    except MassTransferJob.DoesNotExist:
        logger.info("MassTransferJob %d no longer exists; skipping queue.", job_id)
        return

    if job.status != DicomJob.Status.PENDING:
        logger.warning(
            "MassTransferJob %d has status %s (expected PENDING); skipping queue.",
            job_id,
            job.status,
        )
        return

    priority = job.default_priority
    if job.urgent:
        priority = job.urgent_priority

    for mass_task in job.tasks.filter(
        status=DicomTask.Status.PENDING,
        queued_job__isnull=True,  # Skip tasks already queued (idempotency guard)
    ):
        model_label = get_model_label(mass_task.__class__)
        queued_job_id = app.configure_task(
            "adit.mass_transfer.tasks.process_mass_transfer_task",
            allow_unknown=False,
            priority=priority,
        ).defer(model_label=model_label, task_id=mass_task.pk)
        mass_task.queued_job_id = queued_job_id
        mass_task.save()
