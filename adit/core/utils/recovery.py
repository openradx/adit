import logging
from datetime import datetime

from django.apps import apps
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob
from procrastinate.jobs import Status

from ..models import DicomJob, DicomTask

logger = logging.getLogger(__name__)

STALE_TASK_MESSAGE = "The worker processing this task was terminated."

# A worker owns the row and is running it right now.
_RUNNING_ROW_STATUSES = [Status.DOING.value, Status.ABORTING.value]

# Nobody is running the row: it waits to be picked up (todo) or it is finished.
_INACTIVE_ROW_STATUSES = [s.value for s in Status if s.value not in _RUNNING_ROW_STATUSES]

# The row will still fire (or is running): do not create a second one for the same task.
_LIVE_ROW_STATUSES = [Status.TODO.value, *_RUNNING_ROW_STATUSES]

_TERMINAL_JOB_STATUSES = (
    DicomJob.Status.CANCELED,
    DicomJob.Status.SUCCESS,
    DicomJob.Status.WARNING,
    DicomJob.Status.FAILURE,
)


def dicom_task_models() -> list[type[DicomTask]]:
    return [m for m in apps.get_models() if issubclass(m, DicomTask)]


def _owner_gone_q(cutoff: datetime) -> Q:
    """Match tasks whose worker is gone: queue row missing, finished, or worker silent.

    Written as OR-ed positive conditions. An .exclude() over the nullable queued_job
    join would silently drop tasks that have no queue row at all.
    """
    return (
        # queue row deleted (workers run with --delete-jobs=always)
        Q(queued_job__isnull=True)
        # queue row exists but nobody is running it: waiting to be picked up, or finished
        | Q(queued_job__status__in=_INACTIVE_ROW_STATUSES)
        # a worker claimed the row, but its worker record is gone
        | Q(queued_job__status__in=_RUNNING_ROW_STATUSES, queued_job__worker__isnull=True)
        # a worker claimed the row, but stopped sending heartbeats
        | Q(
            queued_job__status__in=_RUNNING_ROW_STATUSES,
            queued_job__worker__last_heartbeat__lt=cutoff,
        )
    )


def _resolve_stale_task(task: DicomTask, owner_gone: Q) -> str | None:
    """Reset one stale task. Returns "pending"/"canceled", or None if it was no longer stale."""
    model = type(task)
    job = task.job

    if job.status in (DicomJob.Status.CANCELING, DicomJob.Status.CANCELED):
        new_status = DicomTask.Status.CANCELED
        end = timezone.now()
    else:
        new_status = DicomTask.Status.PENDING
        end = None

    old_row_id = task.queued_job_id  # the UPDATE below clears the link

    # Reset and re-queue in one transaction: if queuing fails, the reset rolls back and
    # the next sweep tries again. A PENDING task without a queue row would never run.
    with transaction.atomic():
        # The WHERE re-checks status and owner inside the UPDATE itself, so nothing
        # happens if a live worker or another sweep got to this task first.
        updated = (
            model.objects.filter(pk=task.pk, status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .update(status=new_status, message=STALE_TASK_MESSAGE, end=end, queued_job_id=None)
        )
        if not updated:
            return None

        if new_status == DicomTask.Status.PENDING:
            # Re-queue only if the old row will not run again. Read the DB fresh, not our
            # candidate snapshot: the row may have been deleted since we selected the task.
            row_alive = (
                old_row_id is not None
                and ProcrastinateJob.objects.filter(
                    pk=old_row_id, status__in=_LIVE_ROW_STATUSES
                ).exists()
            )
            if not row_alive:
                task.refresh_from_db()  # queue_pending_task() saves the whole task
                task.queue_pending_task()

    return "pending" if new_status == DicomTask.Status.PENDING else "canceled"
