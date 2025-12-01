import uuid

from django.conf import settings
from django.db import models

from adit.core.models import DicomAppSettings


class UploadSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Upload settings"
        default_permissions = ()
        permissions = [
            ("can_upload_data", "Can upload data"),
        ]


class UploadSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_opened = models.DateTimeField(auto_now_add=True)
    upload_size = models.IntegerField(default=0)
    uploaded_file_count = models.IntegerField(default=0)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_jobs",
    )

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"
