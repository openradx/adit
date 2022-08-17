from django.db import models
from django.urls import reverse

import os
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)

from adit.core.models import DicomJob, DicomTask, AppSettings

# Wado  

class DicomWadoSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Dicom Wado settings"


class DicomWadoJob(DicomJob):
    content_type = models.CharField(
        blank=True,
        max_length=64,
    )

    mode = models.CharField(
        blank=True,
        max_length=64,        
    )

    boundary = models.CharField(
        blank=True,
        max_length=64,
    )

    folder_path = models.CharField(
        blank=True,
        max_length=128,
    )

    file_path = models.CharField(
        blank=True,
        max_length=128,
    )

    

    def delay(self):
        from .tasks import process_dicom_wado_job
        process_dicom_wado_job.delay(self.id)
    
    def get_absolute_url(self):
        return reverse("dicom_wado_job_detail", args=[self.job.id, self.task_id])



class DicomWadoTask(DicomTask):
    job = models.ForeignKey(
        DicomWadoJob, on_delete=models.CASCADE, related_name="tasks"
    )
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
    level = models.CharField(
        blank=True,
        max_length=16,
    )

    def get_absolute_url(self):
        return reverse("dicom_wado_task_detail", args=[self.job.id, self.task_id])
