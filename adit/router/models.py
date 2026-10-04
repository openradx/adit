import secrets

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from procrastinate.contrib.django import app

from adit.core.models import (
    DicomAppSettings,
    DicomJob,
    DicomServer,
    DicomTask,
    TransferJob,
    TransferTask,
)
from adit.core.utils.model_utils import get_model_label
from adit.core.utils.series_filters import FilterSpec, parse_filters
from adit.core.validators import ae_title_chars_validator, no_backslash_char_validator


class RouterSettings(DicomAppSettings):
    low_space_mailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Router settings"


class RouterSender(models.Model):
    server_id: int
    server = models.OneToOneField(
        DicomServer, on_delete=models.PROTECT, related_name="router_sender"
    )
    calling_ae_title = models.CharField(
        unique=True,
        max_length=16,
        blank=True,
        default="",
        validators=[ae_title_chars_validator],
        help_text="The AE title the server sends from. Leave empty to use its AE title.",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("calling_ae_title",)

    def __str__(self) -> str:
        return f"Router sender {self.calling_ae_title}"

    def save(self, *args, **kwargs) -> None:
        self.calling_ae_title = self.calling_ae_title.strip() or self.server.ae_title
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.server_id:
            self.calling_ae_title = self.calling_ae_title.strip() or self.server.ae_title
            try:
                ae_title_chars_validator(self.calling_ae_title)
            except ValidationError as err:
                raise ValidationError({"calling_ae_title": err.messages}) from err


class RoutingRule(models.Model):
    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)
    filters_json = models.JSONField(
        help_text="The filters that select the series to send, in the mass transfer format."
    )
    destination_id: int
    destination = models.ForeignKey(DicomServer, on_delete=models.PROTECT, related_name="+")
    pseudonymize = models.BooleanField(default=True)
    pseudonym_salt = models.CharField(max_length=64, blank=True, default=secrets.token_hex)
    trial_protocol_id = models.CharField(
        blank=True,
        default="",
        max_length=64,
        validators=[no_backslash_char_validator],
        help_text="With pseudonymization, XNAT files the images under this project ID.",
    )
    trial_protocol_name = models.CharField(
        blank=True, default="", max_length=64, validators=[no_backslash_char_validator]
    )
    created_by_id: int
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="router_rules"
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    jobs: models.QuerySet["RouterJob"]

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        try:
            self.filters_json = parse_filters(self.filters_json)
        except ValueError as err:
            raise ValidationError({"filters_json": str(err)}) from err

        if not self.pseudonymize:
            self.pseudonym_salt = ""
        elif not self.pseudonym_salt:
            self.pseudonym_salt = secrets.token_hex()

        if self.pk is not None and self.jobs.exists():
            saved = RoutingRule.objects.get(pk=self.pk)
            if (saved.pseudonymize, saved.pseudonym_salt) != (
                self.pseudonymize,
                self.pseudonym_salt,
            ):
                # A patient must keep the same pseudonym under a rule.
                raise ValidationError(
                    "Pseudonymization can't change once the rule has sent studies. "
                    "Create a new rule instead."
                )

        if self.destination_id is not None:
            destination = self.destination
            if not (destination.store_scp_support or destination.dicomweb_stow_support):
                raise ValidationError(
                    {"destination": "The destination must support C-STORE or STOW-RS."}
                )

    def get_filters(self) -> list[FilterSpec]:
        return [FilterSpec.from_dict(d) for d in self.filters_json]

    def retry_failed_deliveries(self) -> tuple[int, int]:
        """Retry the rule's failed deliveries whose images are still in the spool.

        Returns how many deliveries were retried and how many could not be, because the
        images of their batch were deleted.
        """
        retried = not_retriable = 0
        with transaction.atomic():
            failed = self.jobs.filter(status=DicomJob.Status.FAILURE).select_related("batch")
            for job in failed:
                if job.is_retriable:
                    job.retry()
                    retried += 1
                else:
                    not_retriable += 1
        return retried, not_retriable


class RouterBatch(models.Model):
    batch_id = models.UUIDField(unique=True)
    sender_id: int
    sender = models.ForeignKey(RouterSender, on_delete=models.PROTECT, related_name="batches")
    study_instance_uid = models.CharField(max_length=64)
    number_of_images = models.PositiveIntegerField()
    closed_at = models.DateTimeField(auto_now_add=True)
    files_deleted_at = models.DateTimeField(null=True, blank=True)

    jobs: models.QuerySet["RouterJob"]

    class Meta:
        ordering = ("-closed_at",)
        verbose_name_plural = "Router batches"

    def __str__(self) -> str:
        return f"Router batch {self.batch_id}"


class RouterJob(TransferJob):
    default_priority = settings.ROUTER_DEFAULT_PRIORITY
    urgent_priority = settings.ROUTER_URGENT_PRIORITY

    rule_id: int
    rule = models.ForeignKey(RoutingRule, on_delete=models.PROTECT, related_name="jobs")
    batch = models.ForeignKey(RouterBatch, on_delete=models.PROTECT, related_name="jobs")

    tasks: models.QuerySet["RouterTask"]

    class Meta(TransferJob.Meta):
        constraints = [
            models.UniqueConstraint(fields=["rule", "batch"], name="router_unique_rule_batch")
        ]

    def get_absolute_url(self) -> str:
        return reverse("admin:router_routerjob_change", args=[self.pk])

    @property
    def is_deletable(self) -> bool:
        # Canceling stops a delivery and keeps its history.
        return False

    @property
    def is_resumable(self) -> bool:
        # A router job has one task, so Restart covers a canceled job.
        return False

    @property
    def is_retriable(self) -> bool:
        return super().is_retriable and self.batch.files_deleted_at is None

    @property
    def is_restartable(self) -> bool:
        return super().is_restartable and self.batch.files_deleted_at is None

    def queue_pending_tasks(self) -> None:
        assert self.status == DicomJob.Status.PENDING
        for task in self.tasks.filter(status=DicomTask.Status.PENDING):
            task.queue_pending_task()


class RouterTask(TransferTask):
    job = models.ForeignKey(RouterJob, on_delete=models.CASCADE, related_name="tasks")
    sent_instance_uids = ArrayField(models.CharField(max_length=64), blank=True, default=list)

    class Meta(TransferTask.Meta):
        indexes = [models.Index(fields=["study_uid"])]

    def get_absolute_url(self) -> str:
        return reverse("admin:router_routertask_change", args=[self.pk])

    @property
    def is_deletable(self) -> bool:
        # Like its job, a delivery task keeps its history.
        return False

    @property
    def is_resettable(self) -> bool:
        return super().is_resettable and self.job.batch.files_deleted_at is None

    @classmethod
    def already_sent(cls, rule_id: int, study_uid: str, destination_id: int) -> set[str]:
        """The SOP Instance UIDs a rule's finished deliveries sent of a study to a destination."""
        sent: set[str] = set()
        tasks = cls.objects.filter(
            job__rule_id=rule_id,
            study_uid=study_uid,
            destination_id=destination_id,
            status__in=[DicomTask.Status.SUCCESS, DicomTask.Status.WARNING],
        )
        for uids in tasks.values_list("sent_instance_uids", flat=True):
            sent.update(uids)
        return sent

    def queue_pending_task(self) -> None:
        assert self.status == DicomTask.Status.PENDING
        assert self.queued_job is None

        priority = self.job.urgent_priority if self.job.urgent else self.job.default_priority
        queued_job_id = app.configure_task(
            "adit.router.tasks.process_router_task", allow_unknown=False, priority=priority
        ).defer(model_label=get_model_label(self.__class__), task_id=self.pk)
        self.queued_job_id = queued_job_id
        self.save()
