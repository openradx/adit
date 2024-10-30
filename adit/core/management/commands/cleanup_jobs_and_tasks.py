from django.core.management.base import BaseCommand
from django.db.models import Q

from adit.batch_query.models import BatchQueryJob, BatchQueryTask
from adit.batch_transfer.models import BatchTransferJob, BatchTransferTask
from adit.core.models import DicomJob, DicomTask
from adit.selective_transfer.models import SelectiveTransferJob, SelectiveTransferTask


class Command(BaseCommand):
    help = "Cleanup all DICOM jobs and tasks that are stuck."

    def cleanup_tasks(self, model: type[DicomTask]):
        job_ids = set()

        message = "Unexpected crash while processing this task."
        task_log = "The worker crashed unexpectedly and this task was manually set to failed."

        tasks_in_progress = model.objects.filter(status=model.Status.IN_PROGRESS).all()
        for task in tasks_in_progress:
            task.status = SelectiveTransferTask.Status.FAILURE
            task.message = message
            task.log = task_log
            task.save()
            job_ids.add(task.job_id)

        tasks_pending = model.objects.filter(Q(status=model.Status.PENDING)).all()
        for task in tasks_pending:
            if task.queued_job_id is None:
                task.status = SelectiveTransferTask.Status.FAILURE
                task.message = message
                task.log = task_log
                task.save()
                job_ids.add(task.job_id)

        for job_id in job_ids:
            job = SelectiveTransferJob.objects.get(id=job_id)
            job.post_process(suppress_email=True)

    def cleanup_jobs(self, model: type[DicomJob]):
        message = "Unexpected crash while processing this job."

        jobs = model.objects.filter(
            Q(status=model.Status.IN_PROGRESS) | Q(status=model.Status.CANCELING)
        ).all()

        for job in jobs:
            job.status = SelectiveTransferJob.Status.FAILURE
            job.message = message
            job.save()

    def handle(self, *args, **options):
        print("Cleanup DICOM jobs and tasks.")

        print("Make sure workers are idle and no task is currently processed.")
        user_input = input("Are you sure you want to continue? (y/n): ")
        if user_input.lower() not in ("y", "yes"):
            print("Aborting.")
            return

        self.cleanup_tasks(SelectiveTransferTask)
        self.cleanup_jobs(SelectiveTransferJob)
        self.cleanup_tasks(BatchQueryTask)
        self.cleanup_jobs(BatchQueryJob)
        self.cleanup_tasks(BatchTransferTask)
        self.cleanup_jobs(BatchTransferJob)
