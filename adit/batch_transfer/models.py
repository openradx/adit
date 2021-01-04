from django.db import models
from django.urls import reverse
from adit.core.models import AppSettings, TransferJob, BatchTask, TransferTask


class BatchTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Batch transfer settings"


class BatchTransferJob(TransferJob):
    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    @property
    def processed_tasks(self):
        non_processed = (
            BatchTransferTask.Status.PENDING,
            BatchTransferTask.Status.IN_PROGRESS,
        )
        return self.tasks.exclude(status__in=non_processed)

    def delay(self):
        # pylint: disable=import-outside-toplevel
        from .tasks import process_transfer_job

        process_transfer_job.delay(self.id)

    def get_absolute_url(self):
        return reverse("batch_transfer_job_detail", args=[str(self.id)])


class BatchTransferTask(BatchTask, TransferTask):
    class Meta(BatchTask.Meta, TransferTask.Meta):
        unique_together = ("batch_id", "job")

    job = models.ForeignKey(
        BatchTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    def get_absolute_url(self):
        return reverse("batch_transfer_task_detail", args=[str(self.id)])
