from datetime import time
from django.core import validators
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericRelation
from django.urls import reverse
from adit.core.models import AppSettings, TransferJob, TransferTask
from adit.core.validators import (
    no_special_chars_validator,
    no_wildcard_validator,
    no_date_range_validator,
)


def slot_time(hour, minute):
    return time(hour, minute)


class BatchTransferSettings(AppSettings):
    # Must be set in UTC time as Celery workers can't figure out another time zone.
    batch_slot_begin_time = models.TimeField(
        default=slot_time(22, 0),
        help_text=f"Must be set in {settings.TIME_ZONE} time zone.",
    )
    # Must be set in UTC time as Celery workers can't figure out another time zone.
    batch_slot_end_time = models.TimeField(
        default=slot_time(8, 0),
        help_text=f"Must be set in {settings.TIME_ZONE} time zone.",
    )
    batch_timeout = models.IntegerField(default=3)

    class Meta:
        verbose_name_plural = "Batch transfer settings"


class BatchTransferJob(TransferJob):
    JOB_TYPE = "BT"

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    def get_processed_requests(self):
        non_processed = (
            BatchTransferRequest.Status.PENDING,
            BatchTransferRequest.Status.IN_PROGRESS,
        )
        return self.requests.exclude(status__in=non_processed)

    def delay(self):
        from .tasks import batch_transfer  # pylint: disable=import-outside-toplevel

        batch_transfer.delay(self.id)

    def get_absolute_url(self):
        return reverse("batch_transfer_job_detail", args=[str(self.id)])


class BatchTransferRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        WARNING = "WA", "Warning"
        FAILURE = "FA", "Failure"

    class Meta:
        unique_together = ("row_number", "job")
        ordering = ("row_number",)

    job = models.ForeignKey(
        BatchTransferJob, on_delete=models.CASCADE, related_name="requests"
    )
    transfer_tasks = GenericRelation(
        TransferTask, related_query_name="batch_transfer_request"
    )
    row_number = models.PositiveIntegerField()
    patient_id = models.CharField(
        blank=True,
        max_length=64,
        validators=[no_special_chars_validator, no_wildcard_validator],
    )
    patient_name = models.CharField(
        blank=True,
        max_length=324,
        validators=[no_special_chars_validator, no_wildcard_validator],
    )
    patient_birth_date = models.DateField(
        null=True,
        blank=True,
        validators=[no_date_range_validator],
    )
    accession_number = models.CharField(
        blank=True,
        max_length=16,
        validators=[no_special_chars_validator, no_wildcard_validator],
    )
    study_date = models.DateField(
        null=True,
        blank=True,
        validators=[no_date_range_validator],
    )
    modality = models.CharField(
        blank=True,
        max_length=16,
        validators=[no_special_chars_validator, no_wildcard_validator],
    )
    pseudonym = models.CharField(
        blank=True,
        max_length=64,
        validators=[no_special_chars_validator, no_wildcard_validator],
    )
    status = models.CharField(
        max_length=2, choices=Status.choices, default=Status.PENDING
    )
    message = models.TextField(blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    def clean(self):
        errors = []

        if not (self.patient_id or self.patient_name and self.patient_birth_date):
            errors.append(
                ValidationError(
                    "A patient must be identifiable by either a 'Patient ID' "
                    "or a 'Patient Name' combined with a 'Birth Date'."
                )
            )

        if not (self.accession_number or self.study_date and self.modality):
            errors.append(
                ValidationError(
                    "A study must be identifiable by either an 'Accession Number' "
                    "or a 'Study Date' combined with a 'Modality'."
                )
            )

        if len(errors) > 0:
            raise ValidationError(errors)
