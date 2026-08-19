import logging
from datetime import datetime

from django.apps import apps
from django.db.models import Q
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
