from django.urls import reverse
from adit.main.models import AppSettings, TransferJob


class SelectiveTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Selective transfer settings"


class SelectiveTransferJob(TransferJob):
    JOB_TYPE = "ST"

    def delay(self):
        from .tasks import selective_transfer  # pylint: disable=import-outside-toplevel

        selective_transfer.delay(self.id)

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[str(self.id)])
