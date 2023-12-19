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
