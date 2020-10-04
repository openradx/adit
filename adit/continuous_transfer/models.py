from django.db import models
from adit.main.models import TransferJob


class AppSettings(models.Model):
    # Lock the continuous transfer creation form
    continuous_transfer_locked = models.BooleanField(default=False)
    # Suspend the continuous transfer background processing.
    continuous_transfer_suspended = models.BooleanField(default=False)

    @classmethod
    def load(cls):
        return cls.objects.first()

    class Meta:
        verbose_name_plural = "App settings"


class ContinuousTransferJob(TransferJob):
    JOB_TYPE = "CT"

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_type = self.JOB_TYPE
