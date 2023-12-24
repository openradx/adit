from django.conf import settings
from django.db import models
from django.db.models.constraints import UniqueConstraint

from radis.core.models import AppSettings
from radis.reports.models import Report


class NotesAppSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Notes app settings"


class Note(models.Model):
    id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    report_id: int
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    text = models.TextField(blank=True, max_length=10000)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["owner_id", "report_id"],
                name="unique_note_per_user_and_report",
            )
        ]

    def __str__(self) -> str:
        return f"Note {self.id} [{self.report} {self.owner}]"
