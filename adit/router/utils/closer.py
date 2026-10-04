"""The periodic work on the router spool: close, decide, clean up and report."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from adit.core.utils.mail import send_mail_to_admins

from ..models import RouterBatch, RouterJob, RouterSettings, RouterTask
from . import spool
from .routing import decide_batch

logger = logging.getLogger(__name__)

# Files in tmp/ this old were left by a store that failed while writing.
TMP_MAX_AGE_SECONDS = 3600

_FINISHED = (
    RouterJob.Status.SUCCESS,
    RouterJob.Status.WARNING,
    RouterJob.Status.CANCELED,
    RouterJob.Status.FAILURE,
)


def run_spool_cycle(spool_root: Path, now: datetime) -> None:
    """Close the due studies, decide the new batches and clean up the spool."""
    spool.ensure_spool_dirs(spool_root)
    spool.close_due_studies(
        spool_root,
        now.timestamp(),
        settings.ROUTER_QUIET_PERIOD_SECONDS,
        settings.ROUTER_MAX_OPEN_SECONDS,
    )

    today = timezone.localdate(now)
    for batch in spool.list_batches(spool_root):
        try:
            decide_batch(spool_root, batch, today)
        except Exception:
            # One broken batch must not hold up the others; the next run tries it again.
            logger.exception("Could not decide router batch %s.", batch.path)

    delete_finished_batches(spool_root, now)
    spool.clean_quarantine(spool_root, today, settings.ROUTER_QUARANTINE_RETENTION_DAYS)
    spool.clean_old_tmp(spool_root, now.timestamp(), TMP_MAX_AGE_SECONDS)
    mail_if_low_on_space(spool_root, now)


def delete_finished_batches(spool_root: Path, now: datetime) -> int:
    """Delete the folders of batches whose deliveries have all finished.

    A batch with a failed delivery keeps its images for ROUTER_FAILED_RETENTION_DAYS, so
    the delivery can still be retried. Returns how many folders were deleted.
    """
    failed_cutoff = now - timedelta(days=settings.ROUTER_FAILED_RETENTION_DAYS)
    deleted = 0
    batches = RouterBatch.objects.filter(files_deleted_at__isnull=True).prefetch_related("jobs")
    for batch in batches:
        statuses = [job.status for job in batch.jobs.all()]
        if not statuses or any(status not in _FINISHED for status in statuses):
            continue
        if RouterJob.Status.FAILURE in statuses and batch.closed_at > failed_cutoff:
            continue
        spool.delete_batch(spool.batch_dir(spool_root, batch.sender_id, batch.batch_id))
        batch.files_deleted_at = now
        batch.save(update_fields=["files_deleted_at"])
        deleted += 1
    return deleted


def mail_if_low_on_space(spool_root: Path, now: datetime) -> bool:
    """Mail the admins when the spool is low on space, at most once per period."""
    free = spool.free_bytes(spool_root)
    min_free_gb = settings.ROUTER_SPOOL_MIN_FREE_GB
    if free >= min_free_gb * 1024**3:
        return False

    router_settings, _ = RouterSettings.objects.get_or_create()
    last = router_settings.low_space_mailed_at
    if last is not None and now - last < timedelta(hours=settings.ROUTER_LOW_SPACE_MAIL_HOURS):
        return False

    send_mail_to_admins(
        "DICOM router spool low on space",
        f"The DICOM router spool has {free / 1024**3:.1f} GB free, less than "
        f"ROUTER_SPOOL_MIN_FREE_GB ({min_free_gb} GB). The router refuses new images "
        "until space is freed.",
    )
    router_settings.low_space_mailed_at = now
    router_settings.save(update_fields=["low_space_mailed_at"])
    return True


def report_failed_deliveries(now: datetime) -> int:
    """Mail the admins the router deliveries that failed in the last 24 hours."""
    jobs = list(
        RouterJob.objects.filter(status=RouterJob.Status.FAILURE, end__gte=now - timedelta(days=1))
        .select_related("rule", "batch")
        .prefetch_related("tasks")
        .order_by("end")
    )
    if not jobs:
        return 0

    retention = timedelta(days=settings.ROUTER_FAILED_RETENTION_DAYS)
    lines: list[str] = []
    for job in jobs:
        task = next(iter(job.tasks.all()), None)
        reason = task.message if task else job.message
        kept_until = timezone.localdate(job.batch.closed_at + retention)
        lines.append(
            f'- Job {job.pk} of rule "{job.rule.name}", study '
            f"{job.batch.study_instance_uid}: {reason} "
            f"The images stay in the spool until {kept_until}."
        )
    send_mail_to_admins(
        f"{len(jobs)} DICOM router deliveries failed",
        "The DICOM router could not deliver these studies in the last 24 hours:\n\n"
        + "\n".join(lines),
    )
    return len(jobs)


def clear_old_sent_lists(now: datetime) -> int:
    """Forget the images sent by deliveries older than ROUTER_SENT_LIST_RETENTION_DAYS."""
    cutoff = now - timedelta(days=settings.ROUTER_SENT_LIST_RETENTION_DAYS)
    return (
        RouterTask.objects.filter(end__lt=cutoff)
        .exclude(sent_instance_uids=[])
        .update(sent_instance_uids=[])
    )
