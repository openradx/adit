from django.db import models
from django.urls import reverse
from adit.core.models import AppSettings, TransferJob


class SelectiveTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Selective transfer settings"


class SelectiveTransferJob(TransferJob):
    archive_password = models.CharField(blank=True, max_length=50)

    def delay(self):
        from .tasks import selective_transfer  # pylint: disable=import-outside-toplevel

        selective_transfer.delay(self.id)

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[str(self.id)])
