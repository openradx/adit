from datetime import datetime
from django.db import models
from django.urls import reverse
from adit.core.models import AppSettings, DicomJob, DicomTask, BatchTask
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

    def get_absolute_url(self):
        return reverse("batch_query_job_detail", args=[str(self.id)])


class BatchQueryTask(BatchTask, DicomTask):
    class Meta(BatchTask.Meta, DicomTask.Meta):
        unique_together = ("batch_id", "job")

    job = models.ForeignKey(
        BatchQueryJob, on_delete=models.CASCADE, related_name="queries"
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

    def get_absolute_url(self):
        return reverse("batch_query_task_detail", args=[str(self.id)])


class BatchQueryResult(models.Model):
    job = models.ForeignKey(
        BatchQueryJob, on_delete=models.CASCADE, related_name="results"
    )
    query = models.ForeignKey(
        BatchQueryTask, on_delete=models.CASCADE, related_name="results"
    )
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
    accession_number = models.CharField(
        max_length=16,
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

    @property
    def study_date_time(self):
        return datetime.combine(self.study_date, self.study_time)
