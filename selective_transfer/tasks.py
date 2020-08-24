from celery import shared_task, chord
from main.tasks import transfer_dicoms
from main.models import TransferTask
from .models import AppSettings, SelectiveTransferJob


@shared_task(ignore_result=True)
def selective_transfer(job_id):
    job = SelectiveTransferJob.objects.get(id=job_id)

    if job.status != SelectiveTransferJob.Status.PENDING:
        raise AssertionError(f"Invalid job status: {job.get_status_display()}")

    app_settings = AppSettings.load()
    countdown = None
    if app_settings.selective_transfer_suspended:
        countdown = 60 * 60  # 1 hour

    transfer_tasks = [
        transfer_dicoms.s((task.id,), countdown=countdown) for task in job.tasks.all()
    ]

    chord(transfer_tasks)(update_job_status.s(job_id))


@shared_task(ignore_result=True)
def update_job_status(job_id, task_status_list):
    job = SelectiveTransferJob.objects.get(id=job_id)

    has_success = False
    has_failure = False
    for status in task_status_list:
        if status == TransferTask.Status.SUCCESS:
            has_success = True
        elif status == TransferTask.Status.FAILURE:
            has_failure = True
        else:
            raise AssertionError("Invalid task status.")

    if has_success and has_failure:
        job.status = SelectiveTransferJob.Status.WARNING
        job.message = "Some transfer tasks failed."
    elif has_success:
        job.status = SelectiveTransferJob.Status.SUCCESS
        job.message = "All transfer tasks succeeded."
    elif has_failure:
        job.status = SelectiveTransferJob.Status.FAILURE
        job.message = "All transfer tasks failed."
    else:
        raise AssertionError("Invalid task status.")
