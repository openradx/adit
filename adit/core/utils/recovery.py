import logging
from datetime import datetime, timedelta

import pglock
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob
from procrastinate.jobs import Status

from ..models import DicomJob, DicomTask
from .model_utils import DICOM_JOB_POST_PROCESS_LOCK

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

    old_row_id = task.queued_job_id

    # Reset and re-queue in one transaction: if queuing fails, the reset rolls back and
    # the next sweep tries again. A PENDING task without a queue row would never run.
    with transaction.atomic():
        if job.status in (DicomJob.Status.CANCELING, DicomJob.Status.CANCELED):
            # The link is always cleared here: Resume turns CANCELED tasks back into
            # PENDING ones and queues them fresh, which requires a cleared link. If the
            # old row still runs again, it finds the task not PENDING and does nothing.
            updated = (
                model.objects.filter(pk=task.pk, status=DicomTask.Status.IN_PROGRESS)
                .filter(owner_gone)
                .update(
                    status=DicomTask.Status.CANCELED,
                    message=STALE_TASK_MESSAGE,
                    end=timezone.now(),
                    queued_job_id=None,
                )
            )
            return "canceled" if updated else None

        # The WHERE re-checks status and owner inside the UPDATE itself, so nothing
        # happens if a live worker or another sweep got to this task first. The link to
        # the old row is kept: if that row runs the task again, the next sweep must see
        # who owns it — a missing link reads as "owner gone" and would reset a healthy run.
        updated = (
            model.objects.filter(pk=task.pk, status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .update(status=DicomTask.Status.PENDING, message=STALE_TASK_MESSAGE, end=None)
        )
        if not updated:
            return None

        # Re-queue only if the old row will not run again. Read the DB fresh, not our
        # candidate snapshot: the row may have been deleted since we selected the task.
        row_alive = (
            old_row_id is not None
            and ProcrastinateJob.objects.filter(
                pk=old_row_id, status__in=_LIVE_ROW_STATUSES
            ).exists()
        )
        if not row_alive:
            model.objects.filter(pk=task.pk).update(queued_job_id=None)
            task.refresh_from_db()  # queue_pending_task() saves the whole task
            task.queue_pending_task()

    return "pending"


def sweep_stale_dicom_tasks() -> None:
    """Repair tasks left IN_PROGRESS by a killed worker, across all DicomTask models."""
    cutoff = timezone.now() - timedelta(seconds=settings.DICOM_TASK_STALLED_WORKER_GRACE_SECONDS)
    owner_gone = _owner_gone_q(cutoff)

    summary: list[str] = []
    repaired_total = 0
    errors = 0
    affected_jobs: dict[tuple[str, int], DicomJob] = {}

    for model in dicom_task_models():
        pending = canceled = 0
        candidates = (
            model.objects.filter(status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .select_related("job", "queued_job", "queued_job__worker")
        )
        for task in candidates:
            # One broken repair must not stop the sweep; the task stays IN_PROGRESS
            # (the reset rolls back) and the next run tries it again.
            try:
                outcome = _resolve_stale_task(task, owner_gone)
            except Exception:
                logger.exception("Stale task sweep failed to repair %s.", task)
                errors += 1
                continue
            if outcome == "pending":
                pending += 1
            elif outcome == "canceled":
                canceled += 1
            else:
                continue
            affected_jobs[(task.job._meta.label, task.job.pk)] = task.job

        repaired_total += pending + canceled
        total = pending + canceled
        summary.append(f"{model.__name__} {total} ({pending} pending, {canceled} canceled)")

    for job in affected_jobs.values():
        # Recompute the job from its tasks, under the same lock the task finalizer uses.
        # A finished job is recomputed too if it still has open tasks: a repaired task
        # must never hang under a job that already reports a final result.
        # One failing recount must not stop the recounts of the other jobs.
        try:
            with pglock.advisory(DICOM_JOB_POST_PROCESS_LOCK):
                job.refresh_from_db()
                has_open_tasks = job.tasks.filter(
                    status__in=(DicomTask.Status.PENDING, DicomTask.Status.IN_PROGRESS)
                ).exists()
                if job.status not in _TERMINAL_JOB_STATUSES or has_open_tasks:
                    job.post_process()
        except Exception:
            logger.exception("Stale task sweep failed to re-evaluate %s.", job)
            errors += 1

    message = "Stale dicom task sweep: " + ", ".join(summary)
    if repaired_total:
        logger.info(message)
    else:
        logger.debug(message)

    if errors:
        raise RuntimeError(f"Stale dicom task sweep hit {errors} error(s), see logs.")
