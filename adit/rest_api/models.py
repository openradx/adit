import chunk
from django.db import models
import os
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    uid_chars_validator,
    validate_uid_list,
)

from adit.core.models import DicomJob, DicomTask, AppSettings


class DicomWebQIDOSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Dicom web QIDO settings"


class DicomWebQIDOJob(DicomJob):
    format = models.CharField(
        default="JSON",
        max_length=64,
    )

    def delay(self):
        from .tasks import process_dicom_web_qido_job
        process_dicom_web_qido_job.delay(self.id)


class DicomWebQIDOTask(DicomTask):
    job = models.ForeignKey(
        DicomWebQIDOJob, on_delete=models.CASCADE, related_name="tasks"
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


# WADO-RS   
class DicomStudyResponseBodyWriter():
    BOUNDARY = b"adit-boundary"
    CONTENT_TYPE = "application/dicom"
    def write(self, study, binary_file):
        with open(binary_file, "wb") as file:
            for instance in study:
                file.write(b"--" + self.BOUNDARY + b"\r\n")
                file.write(b"Content-Type: application/dicom" + b"\r\n")

                instance = open(instance, "rb")
                while True:
                    chunk = instance.read(1024)
                    if not chunk:
                        break
                    file.write(chunk)

                file.write(b"\r\n")
        
            file.write(b"--" + self.BOUNDARY + b"--")
        
        return binary_file, self.BOUNDARY
            
