"""
Custom Prometheus metrics for ADIT monitoring.

This module defines application-specific metrics for tracking:
- Job and task processing status and duration
- DICOM operations (DIMSE and DICOMweb)
- Task queue depth and retry counts

These metrics complement the built-in django-prometheus metrics and are
scraped by Prometheus via the /metrics endpoint.
"""

from prometheus_client import Counter, Gauge, Histogram

# Job metrics
JOB_STATUS_COUNTER = Counter(
    "adit_job_status_total",
    "Total number of jobs by type and final status",
    ["job_type", "status"],
)

JOB_DURATION_HISTOGRAM = Histogram(
    "adit_job_duration_seconds",
    "Job duration in seconds",
    ["job_type"],
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600, 7200, float("inf")),
)

# Task metrics
TASK_STATUS_COUNTER = Counter(
    "adit_task_status_total",
    "Total number of tasks by type and final status",
    ["task_type", "status"],
)

TASK_QUEUE_DEPTH = Gauge(
    "adit_task_queue_depth",
    "Number of pending tasks in the queue",
    ["queue"],
)

TASK_RETRY_COUNTER = Counter(
    "adit_task_retry_total",
    "Total number of task retries",
    ["task_type"],
)

TASK_DURATION_HISTOGRAM = Histogram(
    "adit_task_duration_seconds",
    "Task duration in seconds",
    ["task_type"],
    buckets=(5, 10, 30, 60, 120, 300, 600, 1200, 1800, float("inf")),
)

# DICOM operation metrics
DICOM_OPERATION_COUNTER = Counter(
    "adit_dicom_operation_total",
    "Total number of DICOM operations",
    ["operation", "server", "status"],
)

DICOM_OPERATION_DURATION = Histogram(
    "adit_dicom_operation_duration_seconds",
    "DICOM operation duration in seconds",
    ["operation", "server"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, float("inf")),
)

# Procrastinate queue metrics
PROCRASTINATE_JOBS_TOTAL = Gauge(
    "adit_procrastinate_jobs_total",
    "Total number of Procrastinate jobs by status",
    ["status"],
)

PROCRASTINATE_QUEUE_SIZE = Gauge(
    "adit_procrastinate_queue_size",
    "Number of jobs in each Procrastinate queue",
    ["queue", "status"],
)
