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
    time_last_accessed = models.DateTimeField(auto_now_add=True)
    total_transfer_size = models.IntegerField(default=0)
    total_number_requests = models.IntegerField(default=0)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_sessions",
    )

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"
