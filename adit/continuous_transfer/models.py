from django.db import models
from django.urls import reverse
from adit.core.models import AppSettings, TransferJob


class ContinuousTransferSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Continuous transfer settings"


class ContinuousTransferJob(TransferJob):
    JOB_TYPE = "CT"
    DEFAULT_PRIORITY = 2
    URGENT_PRIORITY = 6

    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def delay(self):
        from .tasks import (  # pylint: disable=import-outside-toplevel
            continuous_transfer,
        )

        continuous_transfer.delay(self.id)

    def get_absolute_url(self):
        return reverse("continuous_transfer_job_detail", args=[str(self.id)])


class DataElementFilter(models.Model):
    class FilterTypes(models.TextChoices):
        EQUALS = "EQ", "equals"
        EQUALS_NOT = "EN", "equals not"
        CONTAINS = "CO", "contains"
        CONTAINS_NOT = "CN", "contains not"
        REGEX = "RE", "regex"
        REGEX_NOT = "RN", "regex not"

    class Meta:
        ordering = ("order",)

    job = models.ForeignKey(
        ContinuousTransferJob, on_delete=models.CASCADE, related_name="filters"
    )
    dicom_tag = models.CharField(max_length=100)
    filter_type = models.CharField(
        max_length=2, choices=FilterTypes.choices, default=FilterTypes.EQUALS
    )
    filter_value = models.CharField(max_length=200)
    case_sensitive = models.BooleanField(default=False)
    order = models.SmallIntegerField()
