from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class CoreSettings(models.Model):
    id: int
    maintenance_mode = models.BooleanField(default=False)
    announcement = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Core settings"

    def __str__(self):
        return f"{self.__class__.__name__} [ID {self.id}]"

    @classmethod
    def get(cls):
        return cls.objects.first()


class AppSettings(models.Model):
    id: int
    # Lock the creation of new jobs
    locked = models.BooleanField(default=False)
    # Suspend the background processing.
    suspended = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        return cls.objects.first()


class ReportCollection(models.Model):
    if TYPE_CHECKING:
        reports = RelatedManager["SavedReport"]()

    id: int
    name = models.CharField(max_length=255, unique=True)
    note = models.TextField(blank=True)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="report_collections",
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Collection "{self.name}"'


class SavedReport(models.Model):
    id: int
    report_id = models.CharField(max_length=36, unique=True)  # uuid
    note = models.TextField(blank=True)
    collection_id: int
    collection = models.ForeignKey(
        ReportCollection, on_delete=models.CASCADE, related_name="reports"
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Report "{self.report_id}"'
