from django.conf import settings
from django.db import models

from adit.core.models import DicomAppSettings


class DicomWebSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Dicom Web settings"
        permissions = [
            ("can_query", "Can query"),
            ("can_retrieve", "Can retrieve"),
            ("can_store", "Can store"),
        ]


class APISession(models.Model):
    time_opened = models.DateTimeField(auto_now_add=True)
    transfer_size = models.IntegerField(default=0)
    request_type = models.CharField(max_length=50)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_sessions",
    )

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"
