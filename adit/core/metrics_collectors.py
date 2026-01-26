"""
Metrics collection functions for ADIT monitoring.

This module provides functions that collect metrics from the database
and update the Prometheus gauges. These are called periodically by
the collect_metrics task.
"""

import logging

from django.db import connection

from .metrics import (
    PROCRASTINATE_JOBS_TOTAL,
    PROCRASTINATE_QUEUE_SIZE,
    TASK_QUEUE_DEPTH,
)
from .models import DicomTask

logger = logging.getLogger(__name__)


def collect_task_queue_depth() -> None:
    """
    Collect the number of pending DICOM tasks and update the gauge.

    This queries the DicomTask models to count pending tasks grouped by queue.
    """

    try:
        # Count pending tasks in the default queue
        default_queue_count = DicomTask.objects.filter(
            status=DicomTask.Status.PENDING,
        ).count()

        # DICOM tasks are processed in the 'dicom' queue
        TASK_QUEUE_DEPTH.labels(queue="dicom").set(default_queue_count)

        logger.debug("Collected task queue depth: dicom=%d", default_queue_count)
    except Exception:
        logger.exception("Failed to collect task queue depth")


def collect_procrastinate_metrics() -> None:
    """
    Collect metrics from Procrastinate tables.

    This queries the procrastinate_jobs table directly to get queue status.
    """
    try:
        with connection.cursor() as cursor:
            # Count jobs by status
            cursor.execute(
                """
                SELECT status, COUNT(*)
                FROM procrastinate_jobs
                GROUP BY status
                """
            )
            status_counts = dict(cursor.fetchall())

            for status in ["todo", "doing", "succeeded", "failed"]:
                count = status_counts.get(status, 0)
                PROCRASTINATE_JOBS_TOTAL.labels(status=status).set(count)

            # Count jobs by queue and status
            cursor.execute(
                """
                SELECT queue_name, status, COUNT(*)
                FROM procrastinate_jobs
                GROUP BY queue_name, status
                """
            )
            for queue_name, status, count in cursor.fetchall():
                PROCRASTINATE_QUEUE_SIZE.labels(queue=queue_name, status=status).set(count)

            logger.debug("Collected Procrastinate metrics: %s", status_counts)
    except Exception:
        logger.exception("Failed to collect Procrastinate metrics")


def collect_all_metrics() -> None:
    """
    Collect all custom metrics.

    This function is called periodically by the collect_metrics task.
    """
    # collect_task_queue_depth()
    collect_procrastinate_metrics()
