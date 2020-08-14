from datetime import time
from django.db import models
from django.urls import reverse
from main.models import DicomJob


def slot_time(hour, minute):
    return time(hour, minute)


class AppSettings(models.Model):
    # Lock the batch transfer creation form
    batch_transfer_locked = models.BooleanField(default=False)
    # Suspend the batch transfer background processing. Pauses all
    # running job by
    batch_transfer_suspended = models.BooleanField(default=False)
    batch_slot_begin_time = models.TimeField(default=slot_time(22, 0))
    batch_slot_end_time = models.TimeField(default=slot_time(8, 0))
    batch_timeout = models.IntegerField(default=3)

    @classmethod
    def load(cls):
        return cls.objects.first()

    class Meta:
        verbose_name_plural = "App settings"


class BatchTransferJob(DicomJob):
    JOB_TYPE = "BT"

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)
    trial_protocol_id = models.CharField(max_length=64, blank=True)
    trial_protocol_name = models.CharField(max_length=64, blank=True)
    archive_password = models.CharField(max_length=50, blank=True)

    class Meta:
        permissions = (
            ("can_cancel_batchtransferjob", "Can cancel batch transfer job"),
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_type = self.JOB_TYPE

    def get_unprocessed_requests(self):
        return self.requests.filter(status=BatchTransferRequest.Status.UNPROCESSED)

    def get_processed_requests(self):
        return self.requests.exclude(status=BatchTransferRequest.Status.UNPROCESSED)

    def get_successful_requests(self):
        return self.requests.filter(status=BatchTransferRequest.Status.SUCCESS)

    def get_absolute_url(self):
        return reverse("dicom_job_detail", args=[str(self.pk)])


class BatchTransferRequest(models.Model):
    class Status(models.TextChoices):
        UNPROCESSED = "UN", "Unprocessed"
        SUCCESS = "SU", "Success"
        FAILURE = "FA", "Failure"

    class Meta:
        unique_together = ("request_id", "job")

    job = models.ForeignKey(
        BatchTransferJob, on_delete=models.CASCADE, related_name="requests"
    )
    request_id = models.PositiveIntegerField()
    patient_id = models.CharField(null=True, blank=True, max_length=64)
    patient_name = models.CharField(null=True, blank=True, max_length=324)
    patient_birth_date = models.DateField()
    accession_number = models.CharField(null=True, blank=True, max_length=16)
    study_date = models.DateField()
    modality = models.CharField(max_length=16)
    pseudonym = models.CharField(null=True, blank=True, max_length=324)
    status = models.CharField(
        max_length=2, choices=Status.choices, default=Status.UNPROCESSED
    )
    message = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True)
