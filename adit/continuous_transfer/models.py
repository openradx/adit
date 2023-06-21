from typing import TYPE_CHECKING

from celery import current_app
from django.db import models
from django.urls import reverse

from adit.core.models import AppSettings, TransferJob, TransferTask
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    validate_modalities,
    validate_series_numbers,
)

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class ContinuousTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Continuous transfer settings"


class ContinuousTransferJob(TransferJob):
    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)
    study_date_start = models.DateField(
        error_messages={"invalid": "Invalid date format."},
    )
    study_date_end = models.DateField(
        null=True,
        blank=True,
        error_messages={"invalid": "Invalid date format."},
    )
    last_transfer = models.DateTimeField(
        null=True,
        blank=True,
        error_messages={"invalid": "Invalid date format."},
    )
    patient_id = models.CharField(
        blank=True,
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    patient_name = models.CharField(
        blank=True,
        max_length=324,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    patient_birth_date = models.DateField(
        null=True,
        blank=True,
        error_messages={"invalid": "Invalid date format."},
    )
    modalities = models.JSONField(
        null=True,
        blank=True,
        validators=[validate_modalities],
    )
    study_description = models.CharField(
        blank=True,
        max_length=64,
    )
    series_description = models.CharField(
        blank=True,
        max_length=64,
    )
    series_numbers = models.JSONField(
        null=True,
        blank=True,
        validators=[validate_series_numbers],
    )

    if TYPE_CHECKING:
        tasks = RelatedManager["ContinuousTransferTask"]()

    def delay(self):
        current_app.send_task(
            "adit.continuous_transfer.tasks.ProcessContinuousTransferJob", (self.id,)
        )

    def get_absolute_url(self):
        return reverse("continuous_transfer_job_detail", args=[self.id])


class ContinuousTransferTask(TransferTask):
    job = models.ForeignKey(
        ContinuousTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    def get_absolute_url(self):
        return reverse("continuous_transfer_task_detail", args=[self.job.id, self.task_id])
