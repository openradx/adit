from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from radis.core.models import AppSettings

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class CollectionsSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Collection settings"


class ReportCollection(models.Model):
    if TYPE_CHECKING:
        reports = RelatedManager["CollectedReport"]()

    id: int
    name = models.CharField(max_length=255, unique=True)
    note = models.TextField(blank=True)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Collection "{self.name}"'


class CollectedReport(models.Model):
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
