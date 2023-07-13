from datetime import datetime
from typing import TYPE_CHECKING

from celery import current_app
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from adit.core.models import AppSettings, DicomJob, DicomTask
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    pos_int_list_validator,
    validate_modalities,
    validate_series_number,
    validate_series_numbers,
)

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class BatchQuerySettings(AppSettings):
    class Meta:
        verbose_name_plural = "Batch query settings"


class BatchQueryJob(DicomJob):
    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    if TYPE_CHECKING:
        tasks = RelatedManager["BatchQueryTask"]()
        results = RelatedManager["BatchQueryResult"]()

    def delay(self):
        current_app.send_task("adit.batch_query.tasks.ProcessBatchQueryJob", (self.id,))

    def get_absolute_url(self):
        return reverse("batch_query_job_detail", args=[str(self.id)])


class BatchQueryTask(DicomTask):
    job = models.ForeignKey(BatchQueryJob, on_delete=models.CASCADE, related_name="tasks")
    lines = models.TextField(validators=[pos_int_list_validator])
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
    modalities = models.TextField(
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
    series_numbers = models.TextField(
        blank=True,
        validators=[validate_series_numbers],
    )
    pseudonym = models.CharField(  # allow to pipe pseudonym to batch transfer task
        blank=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )

    if TYPE_CHECKING:
        results = RelatedManager["BatchQueryResult"]()

    @property
    def lines_list(self) -> list[str]:
        return list(filter(len, map(str.strip, self.lines.split(","))))

    @lines_list.setter
    def lines_list(self, value: list[str]) -> None:
        self.lines = ", ".join(value)

    @property
    def modalities_list(self) -> list[str]:
        return list(filter(len, map(str.strip, self.modalities.split(","))))

    @modalities_list.setter
    def modalities_list(self, value: list[str]) -> None:
        self.modalities = ", ".join(value)

    @property
    def series_numbers_list(self) -> list[str]:
        return list(filter(len, map(str.strip, self.series_numbers.split(","))))

    @series_numbers_list.setter
    def series_numbers_list(self, value: list[str]) -> None:
        self.series_numbers = ", ".join(value)

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
    id: int
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
    modalities = models.TextField(
        blank=True,
        validators=[validate_modalities],
    )
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
        validators=[
            validate_series_number,
        ],
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

    def __str__(self):
        return f"{self.__class__.__name__} [ID {self.id}]"

    @property
    def modalities_list(self) -> list[str]:
        return list(filter(len, map(str.strip, self.modalities.split(","))))

    @modalities_list.setter
    def modalities_list(self, value: list[str]) -> None:
        self.modalities = ", ".join(value)

    @property
    def study_date_time(self):
        return datetime.combine(self.study_date, self.study_time)
