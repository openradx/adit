from django.conf import settings
from django.db import models
from django.utils import timezone

from adit.core.models import DicomAppSettings


class DicomWebSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Dicom Web settings"
        permissions = [
            ("can_query", "Can query"),
            ("can_retrieve", "Can retrieve"),
            ("can_store", "Can store"),
        ]


class APIUsage(models.Model):
    time_last_accessed = models.DateTimeField(default=timezone.now)
    total_transfer_size = models.BigIntegerField(default=0)
    total_number_requests = models.IntegerField(default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_usage",
    )

    class Meta:
        indexes = [
            models.Index(fields=["-time_last_accessed"]),
        ]
        constraints = [models.UniqueConstraint(fields=["owner"], name="unique_owner_api_usage")]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"
