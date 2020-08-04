from django.db import models
from main.models import DicomJob


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


class SelectiveTransferJob(DicomJob):
    JOB_TYPE = "ST"


class SelectiveTransferRequest(models.Model):
    class Status(models.TextChoices):
        UNPROCESSED = "UN", "Unprocessed"
        SUCCESS = "SU", "Success"
        FAILURE = "FA", "Failure"

    job = models.ForeignKey(
        SelectiveTransferJob, on_delete=models.CASCADE, related_name="requests"
    )
    request_id = models.PositiveIntegerField()
    patient_id = models.CharField(max_length=64)
    study_uid = models.CharField(null=True, max_length=64)
    processed_at = models.DateTimeField(null=True)
