from datetime import datetime

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from adit.core.models import DicomAppSettings, DicomJob, DicomTask
from adit.core.validators import (
    integer_string_validator,
    letters_validator,
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)


class BatchQuerySettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Batch query settings"


class BatchQueryJob(DicomJob):
    default_priority = settings.BATCH_QUERY_DEFAULT_PRIORITY
    urgent_priority = settings.BATCH_QUERY_URGENT_PRIORITY

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)
    
    # Xnat support
    xnat_project_id = models.CharField(
        blank=True,
        max_length=64
    )

    tasks: models.QuerySet["BatchQueryTask"]
    results: models.QuerySet["BatchQueryResult"]

    def get_absolute_url(self):
        return reverse("batch_query_job_detail", args=[str(self.pk)])


class BatchQueryTask(DicomTask):
    job = models.ForeignKey(BatchQueryJob, on_delete=models.CASCADE, related_name="tasks")
    lines = ArrayField(models.PositiveSmallIntegerField())
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
    modalities = ArrayField(
        models.CharField(max_length=16, validators=[letters_validator]),
        blank=True,
        default=list,
    )
    study_description = models.CharField(
        blank=True,
        max_length=64,
    )
    series_description = models.CharField(
        blank=True,
        max_length=64,
    )
    series_numbers = ArrayField(
        models.CharField(max_length=12, validators=[integer_string_validator]),
        blank=True,
        default=list,
    )
    pseudonym = models.CharField(  # allow to pipe pseudonym to batch transfer task
        blank=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )

    results: models.QuerySet["BatchQueryResult"]

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
        return reverse("batch_query_task_detail", args=[self.pk])


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
    modalities = ArrayField(models.CharField(max_length=16, validators=[letters_validator]))
    image_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    study_description = models.CharField(
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
    # Series Number has a VR of Integer String (IS)
    # https://groups.google.com/g/comp.protocols.dicom/c/JNsg7upVJ08
    # https://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html
    series_number = models.CharField(
        blank=True,
        max_length=12,
        validators=[integer_string_validator],
    )
    pseudonym = models.CharField(  # allow to pipe pseudonym through to a possible batch transfer
        blank=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )
    study_uid = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
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

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"

    @property
    def study_date_time(self):
        return datetime.combine(self.study_date, self.study_time)
