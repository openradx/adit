from django.db import models
from django.urls import reverse
from adit.core.models import AppSettings, TransferJob, TransferTask


class SelectiveTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Selective transfer settings"


class SelectiveTransferJob(TransferJob):
    def delay(self):
        # pylint: disable=import-outside-toplevel
        from .tasks import process_transfer_job

        process_transfer_job.delay(self.id)

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[str(self.id)])


class SelectiveTransferTask(TransferTask):
    job = models.ForeignKey(
        SelectiveTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    def get_absolute_url(self):
        return reverse("selective_transfer_task_detail", args=[str(self.id)])
