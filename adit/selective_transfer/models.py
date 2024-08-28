from django.conf import settings
from django.db import models
from django.urls import reverse

from adit.core.models import DicomAppSettings, TransferJob, TransferTask


class SelectiveTransferSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Selective transfer settings"


class SelectiveTransferJob(TransferJob):
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY

    tasks: models.QuerySet["SelectiveTransferTask"]

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[self.id])


class SelectiveTransferTask(TransferTask):
    job = models.ForeignKey(
        SelectiveTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    def get_absolute_url(self):
        return reverse("selective_transfer_task_detail", args=[self.id])
