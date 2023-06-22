from django.db import models
from django.urls import reverse

from adit.core.models import AppSettings, DicomJob, DicomTask
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)


class DicomQidoSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Dicom  Qido settings"


class DicomQidoJob(DicomJob):
    level = models.CharField(
        blank=True,
        max_length=64,
    )

    def delay(self):
        from .tasks import process_dicom_qido_job

        process_dicom_qido_job.delay(self.id)

    def get_absolute_url(self):
        return reverse("dicom_qido_job_detail", args=[self.job.id, self.task_id])


class DicomQidoTask(DicomTask):
    job = models.ForeignKey(DicomQidoJob, on_delete=models.CASCADE, related_name="tasks")
    study_uid = models.CharField(
        blank=True,
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
    query = models.CharField(
        blank=True,
        max_length=2000,
    )


class DicomQidoResult(models.Model):
    job = job = models.ForeignKey(DicomQidoJob, on_delete=models.CASCADE, related_name="results")
    query_results = models.JSONField(default=list)
