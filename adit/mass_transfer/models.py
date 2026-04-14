from __future__ import annotations

import json
import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from procrastinate.contrib.django import app

from adit.core.models import DicomAppSettings, DicomJob, DicomTask, TransferJob, TransferTask
from adit.core.utils.model_utils import get_model_label

if TYPE_CHECKING:
    from .processors import FilterSpec


class MassTransferSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Mass transfer settings"


class MassTransferJob(TransferJob):
    class PartitionGranularity(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    default_priority = settings.MASS_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.MASS_TRANSFER_URGENT_PRIORITY

    start_date = models.DateField()
    end_date = models.DateField()
    partition_granularity = models.CharField(
        max_length=16,
        choices=PartitionGranularity.choices,
        default=PartitionGranularity.DAILY,
    )

    pseudonymize = models.BooleanField(default=True)
    pseudonym_salt = models.CharField(
        max_length=64,
        blank=True,
        default=secrets.token_hex,
    )

    filters_json = models.JSONField(
        blank=True,
        null=True,
        help_text=(
            "JSON list of filter objects. Valid keys: modality, institution_name, "
            "apply_institution_on_study, study_description, series_description, "
            "series_number, min_age, max_age."
        ),
    )

    @property
    def filters_json_pretty(self) -> str:
        if self.filters_json:
            return json.dumps(self.filters_json, indent=2)
        return ""

    def get_filters(self) -> list[FilterSpec]:
        from .processors import FilterSpec

        if not self.filters_json:
            return []
        return [FilterSpec.from_dict(d) for d in self.filters_json]

    tasks: models.QuerySet["MassTransferTask"]

    def get_absolute_url(self):
        return reverse("mass_transfer_job_detail", args=[self.pk])

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be on or after the start date.")
        if not self.pseudonymize:
            self.pseudonym_salt = ""

    def queue_pending_tasks(self):
        """Queues all pending mass transfer tasks via a background job."""
        assert self.status == DicomJob.Status.PENDING

        app.configure_task(
            "adit.mass_transfer.tasks.queue_mass_transfer_tasks",
            allow_unknown=False,
        ).defer(job_id=self.pk)


class MassTransferTask(TransferTask):
    job = models.ForeignKey(
        MassTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    partition_start = models.DateTimeField()
    partition_end = models.DateTimeField()
    partition_key = models.CharField(max_length=64)

    volumes: models.QuerySet["MassTransferVolume"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(partition_start__lt=models.F("partition_end")),
                name="mass_transfer_partition_start_before_end",
            )
        ]

    def get_absolute_url(self):
        return reverse("mass_transfer_task_detail", args=[self.pk])

    def queue_pending_task(self) -> None:
        """Queue this single task on the mass transfer queue."""
        assert self.status == DicomTask.Status.PENDING
        assert self.queued_job is None

        priority = self.job.default_priority
        if self.job.urgent:
            priority = self.job.urgent_priority

        model_label = get_model_label(self.__class__)
        queued_job_id = app.configure_task(
            "adit.mass_transfer.tasks.process_mass_transfer_task",
            allow_unknown=False,
            priority=priority,
        ).defer(model_label=model_label, task_id=self.pk)
        self.queued_job_id = queued_job_id
        self.save()


class MassTransferVolume(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        EXPORTED = "exported", "Exported"
        CONVERTED = "converted", "Converted"
        SKIPPED = "skipped", "Skipped"
        ERROR = "error", "Error"

    job = models.ForeignKey(MassTransferJob, on_delete=models.CASCADE, related_name="volumes")
    task_id: int | None
    task = models.ForeignKey(
        MassTransferTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="volumes",
    )
    partition_key = models.CharField(max_length=64)

    pseudonym = models.CharField(max_length=64, blank=True, default="")
    patient_id = models.CharField(max_length=64, blank=True, default="")
    accession_number = models.CharField(max_length=64, blank=True, default="")
    study_instance_uid = models.CharField(max_length=64)
    study_instance_uid_pseudonymized = models.CharField(max_length=128, blank=True, default="")
    series_instance_uid = models.CharField(max_length=64)
    series_instance_uid_pseudonymized = models.CharField(max_length=128, blank=True, default="")
    modality = models.CharField(max_length=16, blank=True, default="")
    study_description = models.CharField(max_length=256, blank=True, default="")
    series_description = models.CharField(max_length=256, blank=True, default="")
    series_number = models.IntegerField(null=True, blank=True)
    study_datetime = models.DateTimeField()
    institution_name = models.CharField(max_length=128, blank=True, default="")
    number_of_images = models.PositiveIntegerField(default=0)

    converted_file = models.TextField(blank=True, default="")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    log = models.TextField(blank=True, default="")

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("study_datetime", "series_instance_uid")
        constraints = [
            models.UniqueConstraint(
                fields=["job", "series_instance_uid"],
                name="mass_transfer_unique_series_per_job",
            )
        ]

    def __str__(self) -> str:
        return f"MassTransferVolume {self.series_instance_uid}"

    def add_log(self, msg: str) -> None:
        if self.log:
            self.log += "\n"
        self.log += msg


