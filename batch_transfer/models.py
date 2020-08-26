from datetime import time
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.urls import reverse
from main.models import TransferJob, TransferTask


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


class BatchTransferJob(TransferJob):
    JOB_TYPE = "BT"

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    class Meta:
        permissions = (("cancel_batchtransferjob", "Can cancel batch transfer job"),)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_type = self.JOB_TYPE

    def get_processed_requests(self):
        return self.requests.exclude(status=BatchTransferRequest.Status.PENDING)

    def get_absolute_url(self):
        return reverse("transfer_job_detail", args=[str(self.pk)])


class BatchTransferRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        FAILURE = "FA", "Failure"

    class Meta:
        unique_together = ("request_id", "job")

    job = models.ForeignKey(
        BatchTransferJob, on_delete=models.CASCADE, related_name="requests"
    )
    transfer_tasks = GenericRelation(
        TransferTask, related_query_name="batch_transfer_request"
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
        max_length=2, choices=Status.choices, default=Status.PENDING
    )
    message = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True)
