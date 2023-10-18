from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.db.models.constraints import UniqueConstraint

from radis.api.serializers import DOCUMENT_ID_MAX_LENGTH
from radis.core.models import AppSettings

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class CollectionsAppSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Collections app settings"


class CollectionManager(models.Manager):
    def get_last_used_collection(self, owner_id: int):
        return Collection.objects.filter(owner_id=owner_id).order_by("-reports__created").first()


class Collection(models.Model):
    if TYPE_CHECKING:
        reports = RelatedManager["CollectedReport"]()

    id: int
    name = models.CharField(max_length=64)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
    )
    created = models.DateTimeField(auto_now_add=True)

    objects: CollectionManager = CollectionManager()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["name", "owner_id"],
                name="unique_collection_name_per_user",
            )
        ]

    def __str__(self):
        return f"Collection {self.id} [{self.name}]"


class CollectedReportManager(models.Manager):
    def get_collection_counts(self, owner_id: int, document_ids: list[str]) -> dict[str, int]:
        results = (
            CollectedReport.objects.filter(
                collection__owner_id=owner_id, document_id__in=document_ids
            )
            .values("document_id")
            .annotate(total=Count("document_id"))
            .order_by("total")
        )

        collection_count_per_report = {result["document_id"]: result["total"] for result in results}

        for document_id in document_ids:
            if document_id not in collection_count_per_report:
                collection_count_per_report[document_id] = 0

        return collection_count_per_report


class CollectedReport(models.Model):
    id: int
    document_id = models.CharField(max_length=DOCUMENT_ID_MAX_LENGTH)
    collection_id: int
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="reports")
    created = models.DateTimeField(auto_now_add=True)

    objects: CollectedReportManager = CollectedReportManager()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["document_id", "collection_id"],
                name="unique_document_per_collection",
            )
        ]

    def __str__(self):
        return f"CollectedReport {self.id} [{self.document_id}]"
