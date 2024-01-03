from datetime import datetime
from typing import TYPE_CHECKING

from celery import current_app
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from adit.core.models import AppSettings, TransferJob, TransferTask
from adit.core.validators import (
    integer_string_validator,
    letters_validator,
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
# Create your models here.


class UploadSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Upload settings"


class UploadJob(TransferJob):
    if TYPE_CHECKING:
        tasks = RelatedManager["UploadTask"]()
        # pseudoynm = models.CharField()
        # data_folder_path = models.CharField()

    def get_absolute_url(self):
        return reverse("upload_job__detail", args=[self.id])


class UploadTask(TransferTask):
    job = models.ForeignKey(UploadJob, on_delete=models.CASCADE, related_name="tasks")
