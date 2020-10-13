from django.db import models
from django.urls import reverse
import celery
from adit.main.models import TransferJob


class AppSettings(models.Model):
    # Lock the selective transfer creation form
    selective_transfer_locked = models.BooleanField(default=False)
    # Suspend the selective transfer background processing.
    selective_transfer_suspended = models.BooleanField(default=False)

    @classmethod
    def load(cls):
        return cls.objects.first()

    class Meta:
        verbose_name_plural = "App settings"


class SelectiveTransferJob(TransferJob):
    JOB_TYPE = "ST"

    def delay(self):
        celery.current_app.send_task(
            "adit.selective_transfer.tasks.selective_transfer", (self.id,)
        )

    def get_absolute_url(self):
        return reverse("selective_transfer_job_detail", args=[str(self.id)])
