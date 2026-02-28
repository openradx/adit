from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse
from procrastinate.contrib.django import app

from adit.core.models import DicomAppSettings, DicomJob, DicomNode, DicomTask
from adit.core.utils.model_utils import get_model_label


class MassTransferSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Mass transfer settings"


class MassTransferFilter(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mass_transfer_filters",
    )
    name = models.CharField(max_length=150)
    modality = models.CharField(max_length=16, blank=True, default="")
    institution_name = models.CharField(max_length=128, blank=True, default="")
    apply_institution_on_study = models.BooleanField(default=True)
    study_description = models.CharField(max_length=256, blank=True, default="")
    series_description = models.CharField(max_length=256, blank=True, default="")
    series_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="mass_transfer_filter_name_not_blank",
            ),
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="mass_transfer_filter_unique_owner_name",
            ),
        ]

    def __str__(self) -> str:
        if self.name:
            return self.name

        parts: list[str] = []
        if self.modality:
            parts.append(self.modality)
        if self.institution_name:
            parts.append(f"Institution={self.institution_name}")
        if self.study_description:
            parts.append(f"Study={self.study_description}")
        if self.series_description:
            parts.append(f"Series={self.series_description}")
        if self.series_number is not None:
            parts.append(f"SeriesNumber={self.series_number}")

        return "; ".join(parts) if parts else f"Filter #{self.pk}"


class MassTransferJob(DicomJob):
    class PartitionGranularity(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    class AnonymizationMode(models.TextChoices):
        NONE = "none", "No anonymization"
        PSEUDONYMIZE = "pseudonymize", "Pseudonymize"
        PSEUDONYMIZE_WITH_LINKING = "pseudonymize_with_linking", "Pseudonymize with linking"

    default_priority = settings.MASS_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.MASS_TRANSFER_URGENT_PRIORITY

    source = models.ForeignKey(DicomNode, related_name="+", on_delete=models.PROTECT)
    destination = models.ForeignKey(DicomNode, related_name="+", on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    partition_granularity = models.CharField(
        max_length=16,
        choices=PartitionGranularity.choices,
        default=PartitionGranularity.DAILY,
    )
    anonymization_mode = models.CharField(
        max_length=32,
        choices=AnonymizationMode.choices,
        default=AnonymizationMode.PSEUDONYMIZE,
    )

    filters = models.ManyToManyField(MassTransferFilter, related_name="jobs", blank=True)

    @property
    def should_pseudonymize(self) -> bool:
        return self.anonymization_mode != self.AnonymizationMode.NONE

    @property
    def should_link(self) -> bool:
        return self.anonymization_mode == self.AnonymizationMode.PSEUDONYMIZE_WITH_LINKING

    tasks: models.QuerySet["MassTransferTask"]

    def get_absolute_url(self):
        return reverse("mass_transfer_job_detail", args=[self.pk])

    def queue_pending_tasks(self):
        """Queues all pending mass transfer tasks."""
        assert self.status == DicomJob.Status.PENDING

        priority = self.default_priority
        if self.urgent:
            priority = self.urgent_priority

        for mass_task in self.tasks.filter(status=DicomTask.Status.PENDING):
            assert mass_task.queued_job is None

            model_label = get_model_label(mass_task.__class__)
            queued_job_id = app.configure_task(
                "adit.core.tasks.process_mass_transfer_task",
                allow_unknown=False,
                priority=priority,
            ).defer(model_label=model_label, task_id=mass_task.pk)
            mass_task.queued_job_id = queued_job_id
            mass_task.save()


class MassTransferTask(DicomTask):
    job = models.ForeignKey(
        MassTransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    partition_start = models.DateTimeField()
    partition_end = models.DateTimeField()
    partition_key = models.CharField(max_length=64)

    volumes: models.QuerySet["MassTransferVolume"]

    def get_absolute_url(self):
        return reverse("mass_transfer_task_detail", args=[self.pk])

    def cleanup_on_failure(self) -> None:
        """Clean up exported DICOM files when a mass transfer task fails or times out."""
        volumes = self.volumes.exclude(exported_folder="")

        for volume in volumes:
            if volume.status == MassTransferVolume.Status.CONVERTED:
                continue
            # When not converting to NIfTI, EXPORTED is the final state and
            # the files live in the destination folder — don't delete them.
            if (
                not self.job.convert_to_nifti
                and volume.status == MassTransferVolume.Status.EXPORTED
            ):
                continue

            export_folder = volume.exported_folder
            if export_folder:
                try:
                    shutil.rmtree(Path(export_folder))
                except FileNotFoundError:
                    pass
                except Exception as err:
                    volume.add_log(f"Cleanup failed: {err}")
                    volume.save()
                    continue

            volume.exported_folder = ""
            volume.status = MassTransferVolume.Status.ERROR
            volume.add_log("Export cleaned up after task failure.")
            volume.save()


class MassTransferVolume(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        EXPORTED = "exported", "Exported"
        CONVERTED = "converted", "Converted"
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
    series_instance_uid = models.CharField(max_length=64)
    modality = models.CharField(max_length=16, blank=True, default="")
    study_description = models.CharField(max_length=256, blank=True, default="")
    series_description = models.CharField(max_length=256, blank=True, default="")
    series_number = models.IntegerField(null=True, blank=True)
    study_datetime = models.DateTimeField()
    institution_name = models.CharField(max_length=128, blank=True, default="")
    number_of_images = models.PositiveIntegerField(default=0)

    exported_folder = models.TextField(blank=True, default="")
    export_cleaned = models.BooleanField(default=False)
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


class MassTransferAssociation(models.Model):
    """Maps original DICOM UIDs to their pseudonymized counterparts for longitudinal linking."""

    job = models.ForeignKey(
        MassTransferJob,
        on_delete=models.CASCADE,
        related_name="associations",
    )
    task = models.ForeignKey(
        MassTransferTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="associations",
    )
    pseudonym = models.CharField(max_length=64)
    patient_id = models.CharField(max_length=64)
    original_study_instance_uid = models.CharField(max_length=128)
    pseudonymized_study_instance_uid = models.CharField(max_length=128)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["job", "original_study_instance_uid"],
                name="mass_transfer_unique_association_per_study",
            )
        ]

    def __str__(self) -> str:
        return (
            f"MassTransferAssociation {self.original_study_instance_uid} "
            f"-> {self.pseudonymized_study_instance_uid}"
        )
