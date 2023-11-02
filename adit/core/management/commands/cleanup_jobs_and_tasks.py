from django.core.management.base import BaseCommand
from django.db.models import Q

from adit.batch_query.models import BatchQueryJob, BatchQueryTask
from adit.batch_transfer.models import BatchTransferJob, BatchTransferTask
from adit.selective_transfer.models import SelectiveTransferJob, SelectiveTransferTask


class Command(BaseCommand):
    help = (
        "Cleanup all DICOM jobs and tasks by setting those with a PENDING or IN_PROGRESS"
        "status (maybe because of some previous worker crash) to a FAILURE status."
    )

    def handle(self, *args, **options):
        print("Cleanup DICOM jobs and tasks.")

        def reset_tasks(
            model: type[SelectiveTransferTask] | type[BatchQueryTask] | type[BatchTransferTask],
        ):
            message = "Unexpected crash while processing this task."
            task_log = "The worker crashed unexpectedly and this task was manually set to failed."

            tasks = model.objects.filter(
                Q(status=model.Status.IN_PROGRESS) | Q(status=model.Status.PENDING)
            ).all()

            for task in tasks:
                task.status = SelectiveTransferTask.Status.FAILURE
                task.message = message
                task.log = task_log
                task.save()

        def reset_jobs(
            model: type[SelectiveTransferJob] | type[BatchQueryJob] | type[BatchTransferJob],
        ):
            message = "Unexpected crash while processing this job."

            jobs = model.objects.filter(
                Q(status=model.Status.IN_PROGRESS) | Q(status=model.Status.PENDING)
            ).all()

            for job in jobs:
                job.status = SelectiveTransferJob.Status.FAILURE
                job.message = message
                job.save()

        reset_tasks(SelectiveTransferTask)
        reset_jobs(SelectiveTransferJob)
        reset_tasks(BatchQueryTask)
        reset_jobs(BatchQueryJob)
        reset_tasks(BatchTransferTask)
        reset_jobs(BatchTransferJob)
