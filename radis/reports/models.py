from typing import TYPE_CHECKING

from django.contrib.auth.models import Group
from django.contrib.postgres.fields import ArrayField
from django.db import models

from radis.accounts.models import User
from radis.core.models import AppSettings
from radis.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    validate_patient_sex,
)

if TYPE_CHECKING:
    from django.db.models import manager

    from radis.collections.models import Collection


class ReportsAppSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Reports app settings"


class Report(models.Model):
    id: int
    document_id = models.CharField(max_length=128, unique=True)
    groups = models.ManyToManyField(
        Group,
        related_name="reports",
    )
    pacs_aet = models.CharField(max_length=16)
    pacs_name = models.CharField(max_length=64)
    patient_id = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    patient_birth_date = models.DateField()
    patient_sex = models.CharField(
        max_length=1,
        validators=[validate_patient_sex],
    )
    study_instance_uid = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    accession_number = models.CharField(
        blank=True,
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    study_description = models.CharField(blank=True, max_length=64)
    study_datetime = models.DateTimeField()
    series_instance_uid = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    modalities_in_study = ArrayField(models.CharField(max_length=16))
    sop_instance_uid = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    references = ArrayField(models.URLField())
    body = models.TextField()

    if TYPE_CHECKING:
        collections = manager.RelatedManager["Collection"]()

    def __str__(self) -> str:
        return f"Report {self.id} [{self.document_id}]"

    def get_collections(self, owner: User) -> models.QuerySet["Collection"]:
        return self.collections.filter(owner=owner)

    def get_collections_count(self, owner: User) -> int:
        return self.get_collections(owner).count()
