from django.db import models
from main.models import TransferJob


class AppSettings(models.Model):
    # Lock the batch transfer creation form
    selective_transfer_locked = models.BooleanField(default=False)
    # Suspend the batch transfer background processing. Pauses all
    # running job by
    selective_transfer_suspended = models.BooleanField(default=False)

    @classmethod
    def load(cls):
        return cls.objects.first()

    class Meta:
        verbose_name_plural = "App settings"


class SelectiveTransferJob(TransferJob):
    JOB_TYPE = "ST"
