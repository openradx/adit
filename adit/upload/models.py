from django.db import models

from adit.core.models import DicomAppSettings


class UploadSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Upload settings"


class UploadPermissionSupport(models.Model):
    id: int

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("can_upload_data", "Can upload data"),
        ]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [ID {self.id}]"
