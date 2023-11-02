from ..models import DicomJob, DicomTask


def update_job_status(dicom_job: DicomJob):
    """Evaluates all the tasks of a dicom job and sets the job status accordingly."""

    if dicom_job.tasks.filter(status=DicomTask.Status.PENDING).exists():
        if dicom_job.status != DicomJob.Status.CANCELING:
            dicom_job.status = DicomJob.Status.PENDING
    elif dicom_job.tasks.filter(status=DicomTask.Status.IN_PROGRESS).exists():
        if dicom_job.status != DicomJob.Status.CANCELING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
    elif dicom_job.status == DicomJob.Status.CANCELING:
        dicom_job.status = DicomJob.Status.CANCELED
    else:
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
