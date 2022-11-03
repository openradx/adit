from datetime import datetime
from celery import current_app
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from adit.core.models import AppSettings, DicomJob, DicomTask
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    validate_modalities,
)


class BatchQuerySettings(AppSettings):
    class Meta:
        verbose_name_plural = "Batch query settings"


class BatchQueryJob(DicomJob):
    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    def delay(self):
        current_app.send_task("adit.selective_transfer.tasks.ProcessBatchQueryJob", (self.id,))

    def get_absolute_url(self):
        return reverse("batch_query_job_detail", args=[str(self.id)])


class BatchQueryTask(DicomTask):
    job = models.ForeignKey(BatchQueryJob, on_delete=models.CASCADE, related_name="tasks")
    lines = models.JSONField(default=list)
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
    # Accession Number is of VR SH (Short String) and allows only 16 chars max.
    # Unfortunately some accession numbers in our PACS are longer (not DICOM
    # conform) so we use 32 characters.
    accession_number = models.CharField(
        blank=True,
        max_length=32,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    study_date_start = models.DateField(
        null=True,
        blank=True,
        error_messages={"invalid": "Invalid date format."},
    )
    study_date_end = models.DateField(
        null=True,
        blank=True,
        error_messages={"invalid": "Invalid date format."},
    )
    modalities = models.JSONField(
        null=True,
        blank=True,
        validators=[validate_modalities],
    )
    pseudonym = models.CharField(  # allow to pipe pseudonym through to a possible batch transfer
        blank=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )
    series_description = models.CharField(
        blank=True,
        max_length=64,
    )
    series_number = models.CharField(
        blank=True,
        max_length=32,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )

    def clean(self) -> None:
        if not self.accession_number and not self.modalities:
            raise ValidationError("Missing Modality.")

        if not self.patient_id and not (self.patient_name and self.patient_birth_date):
            raise ValidationError(
                "A patient must be identifiable by either PatientID or "
                "PatientName and PatientBirthDate."
            )

        return super().clean()

    def get_absolute_url(self):
        return reverse("batch_query_task_detail", args=[self.job.id, self.task_id])


class BatchQueryResult(models.Model):
    job = models.ForeignKey(BatchQueryJob, on_delete=models.CASCADE, related_name="results")
    query = models.ForeignKey(BatchQueryTask, on_delete=models.CASCADE, related_name="results")
    patient_id = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    patient_name = models.CharField(
        max_length=324,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    patient_birth_date = models.DateField()
    study_uid = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    # See note of accession_number field in BatchQueryTask
    accession_number = models.CharField(
        max_length=32,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    study_date = models.DateField()
    study_time = models.TimeField()
    study_description = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    modalities = models.JSONField(
        null=True,
        blank=True,
        validators=[validate_modalities],
    )
    image_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    pseudonym = models.CharField(  # allow to pipe pseudonym through to a possible batch transfer
        blank=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )
    series_uid = models.CharField(
        blank=True,
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    series_description = models.CharField(
        blank=True,
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    series_number = models.CharField(
        blank=True,
        max_length=32,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )

    @property
    def study_date_time(self):
        return datetime.combine(self.study_date, self.study_time)
