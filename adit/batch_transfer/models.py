from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse

from adit.core.models import DicomAppSettings, TransferJob, TransferTask


class BatchTransferSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Batch transfer settings"


class BatchTransferJob(TransferJob):
    default_priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.BATCH_TRANSFER_URGENT_PRIORITY

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)
    ethics_application_id = models.CharField(blank=True, max_length=100)

    tasks: models.QuerySet["BatchTransferTask"]

    def get_absolute_url(self):
        return reverse("batch_transfer_job_detail", args=[self.id])


class BatchTransferTask(TransferTask):
    job = models.ForeignKey(
        BatchTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    lines = ArrayField(models.PositiveSmallIntegerField())

    def get_absolute_url(self):
        return reverse("batch_transfer_task_detail", args=[self.id])
