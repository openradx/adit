from typing import TYPE_CHECKING

from celery import current_app
from django.db import models
from django.urls import reverse

from adit.core.models import AppSettings, TransferJob, TransferTask

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class SelectiveTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Selective transfer settings"


class SelectiveTransferJob(TransferJob):
    if TYPE_CHECKING:
        tasks = RelatedManager["SelectiveTransferTask"]()

    def delay(self):
        current_app.send_task(
            "adit.selective_transfer.tasks.ProcessSelectiveTransferJob", (self.id,)
        )

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[self.id])


class SelectiveTransferTask(TransferTask):
    job = models.ForeignKey(
        SelectiveTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    def get_absolute_url(self):
        return reverse("selective_transfer_task_detail", args=[self.job.id, self.task_id])
