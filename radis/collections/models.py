from django.conf import settings
from django.db import models
from django.db.models.constraints import UniqueConstraint

from radis.core.models import AppSettings
from radis.reports.models import Report


class CollectionsAppSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Collections app settings"


class CollectionQuerySet(models.QuerySet["Collection"]):
    def with_has_report(self, report_id: int):
        return self.order_by("name").annotate(
            has_report=models.Exists(
                Collection.objects.filter(
                    id=models.OuterRef("id"),
                    reports__id=report_id,
                )
            )
        )


class CollectionManager(models.Manager["Collection"]):
    def get_queryset(self) -> CollectionQuerySet:
        return CollectionQuerySet(self.model)

    def with_has_report(self, report_id: int):
        return self.get_queryset().with_has_report(report_id)


class Collection(models.Model):
    id: int
    name = models.CharField(max_length=64)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
    )
    reports = models.ManyToManyField(
        Report,
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
