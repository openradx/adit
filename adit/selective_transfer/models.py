from django.urls import reverse
import celery
from adit.main.models import AppSettings, TransferJob


class SelectiveTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Selective transfer settings"


class SelectiveTransferJob(TransferJob):
    JOB_TYPE = "ST"

    def delay(self):
        celery.current_app.send_task(
            "adit.selective_transfer.tasks.selective_transfer", (self.id,)
        )

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[str(self.id)])
