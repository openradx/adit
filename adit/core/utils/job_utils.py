from ..models import DicomJob, DicomTask, QueuedTask


def queue_pending_task(dicom_task: DicomTask, default_priority: int, urgent_priority: int) -> None:
    """Queues a dicom task."""
    priority = default_priority
    if dicom_task.job.urgent:
        priority = urgent_priority

    if not dicom_task.queued:
        QueuedTask.objects.create(content_object=dicom_task, priority=priority)


def queue_pending_tasks(dicom_job: DicomJob, default_priority: int, urgent_priority: int) -> None:
    """Queues all the pending tasks of a dicom job."""
    priority = default_priority
    if dicom_job.urgent:
        priority = urgent_priority

    for dicom_task in dicom_job.tasks.filter(status=DicomTask.Status.PENDING):
        if not dicom_task.queued:
            QueuedTask.objects.create(content_object=dicom_task, priority=priority)


def update_job_status(dicom_job: DicomJob) -> bool:
    """Evaluates all the tasks of a dicom job and sets the job status accordingly.

    Returns: True if the job is finished, False otherwise
    """

    if dicom_job.tasks.filter(status=DicomTask.Status.PENDING).exists():
        if dicom_job.status != DicomJob.Status.CANCELING:
            dicom_job.status = DicomJob.Status.PENDING
        return False

    if dicom_job.tasks.filter(status=DicomTask.Status.IN_PROGRESS).exists():
        if dicom_job.status != DicomJob.Status.CANCELING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
        return False

    if dicom_job.status == DicomJob.Status.CANCELING:
        dicom_job.status = DicomJob.Status.CANCELED
        return False

    # Job is finished and we evaluate its final status
    has_success = dicom_job.tasks.filter(status=DicomTask.Status.SUCCESS).exists()
    has_warning = dicom_job.tasks.filter(status=DicomTask.Status.WARNING).exists()
    has_failure = dicom_job.tasks.filter(status=DicomTask.Status.FAILURE).exists()

    if has_success and not has_warning and not has_failure:
        dicom_job.status = DicomJob.Status.SUCCESS
        dicom_job.message = "All tasks succeeded."
    elif has_success and has_failure or has_warning and has_failure:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "Some tasks failed."
    elif has_success and has_warning:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "Some tasks have warnings."
    elif has_warning:
        dicom_job.status = DicomJob.Status.WARNING
        dicom_job.message = "All tasks have warnings."
    elif has_failure:
        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "All tasks failed."
    else:
        # at least one of success, warnings or failures must be > 0
        raise AssertionError(f"Invalid task status list of {dicom_job}.")
    return True
