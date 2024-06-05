from typing import TYPE_CHECKING

from django.db import models
from django.urls import reverse

from adit.core.models import DicomAppSettings, TransferJob, TransferTask

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
# Create your models here.


class UploadSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Upload settings"


class UploadJob(TransferJob):
    # class exists only because the UploadJobForm is a ModelForm
    # from which the allowed DicomNodes of the currently logged in user are needed for data upload.

    if TYPE_CHECKING:
        tasks = RelatedManager["UploadTask"]()

    def get_absolute_url(self):
        return reverse("upload_job__detail", args=[self.id])


class UploadTask(TransferTask):
    job = models.ForeignKey(UploadJob, on_delete=models.CASCADE, related_name="tasks")
