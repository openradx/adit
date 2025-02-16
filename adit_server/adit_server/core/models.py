from typing import Callable, Literal, TypeVar

from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.models import AppSettings
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.constraints import UniqueConstraint
from django.utils import timezone
from procrastinate.contrib.django import app
from procrastinate.contrib.django.models import ProcrastinateJob

from .utils.mail import send_job_finished_mail
from .utils.model_utils import get_model_label, reset_tasks
from .validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    uid_chars_validator,
)


class DicomAppSettings(AppSettings):
    suspended = models.BooleanField(default=False)

    class Meta:
        abstract = True


TModel = TypeVar("TModel", bound=models.Model)


class DicomNodeManager(models.Manager[TModel]):
    def accessible_by_user(
        self, user: User, access_type: Literal["source", "destination"], all_groups: bool = False
    ) -> models.QuerySet[TModel]:
        """Check if the user is allowed to access the given node.

        Args:
            user: The user to check for access to the node.
            access_type: The type of access to check ("source" or "destination").
            all_groups: Check over all groups of the user, otherwise only the active group.

        Returns:
            A queryset of nodes that the user is allowed to access.
        """
        if all_groups:
            accessible_nodes = self.filter(accesses__group__in=user.groups.all())
        else:
            accessible_nodes = self.filter(accesses__group=user.active_group)
        if access_type == "source":
            accessible_nodes = accessible_nodes.filter(accesses__source=True)
        elif access_type == "destination":
            accessible_nodes = accessible_nodes.filter(accesses__destination=True)
        else:
            raise AssertionError(f"Invalid node type: {access_type}")

        return accessible_nodes.distinct()


class DicomNode(models.Model):
    class NodeType(models.TextChoices):
        SERVER = "SV", "Server"
        FOLDER = "FO", "Folder"

    NODE_TYPE: NodeType

    dicomserver: "DicomServer"
    dicomfolder: "DicomFolder"

    node_type = models.CharField(max_length=2, choices=NodeType.choices)
    name = models.CharField(unique=True, max_length=64)
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="dicom_nodes",
        through="DicomNodeGroupAccess",
    )

    objects: DicomNodeManager["DicomNode"] = DicomNodeManager["DicomNode"]()

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        node_types_dict = dict(self.NodeType.choices)
        return f"DICOM {node_types_dict[self.node_type]} {self.name}"

    def __repr__(self) -> str:
        return f"{self.__str__()} [{self.pk}]"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.node_type:
            if self.NODE_TYPE not in dict(self.NodeType.choices):
                raise AssertionError(f"Invalid node type: {self.NODE_TYPE}")
            self.node_type = self.NODE_TYPE

    def is_accessible_by_user(
        self, user: User, access_type: Literal["source", "destination"]
    ) -> bool:
        return DicomNode.objects.accessible_by_user(user, access_type).filter(pk=self.pk).exists()


class DicomNodeGroupAccess(models.Model):
    dicom_node = models.ForeignKey(DicomNode, on_delete=models.CASCADE, related_name="accesses")
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    source = models.BooleanField(default=False)
    destination = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "DICOM node group accesses"
        constraints = [
            UniqueConstraint(
                fields=["dicom_node", "group"],
                name="unique_dicom_node_per_group",
            )
        ]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"


class DicomServer(DicomNode):
    NODE_TYPE = DicomNode.NodeType.SERVER

    # traditional DICOM support
    ae_title = models.CharField(unique=True, max_length=16)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(65535)])
    patient_root_find_support = models.BooleanField(default=False)
    patient_root_get_support = models.BooleanField(default=False)
    patient_root_move_support = models.BooleanField(default=False)
    study_root_find_support = models.BooleanField(default=False)
    study_root_get_support = models.BooleanField(default=False)
    study_root_move_support = models.BooleanField(default=False)
    store_scp_support = models.BooleanField(default=False)

    # (optional) DICOMweb support
    dicomweb_root_url = models.CharField(blank=True, max_length=2000)
    dicomweb_qido_support = models.BooleanField(default=False)
    dicomweb_wado_support = models.BooleanField(default=False)
    dicomweb_stow_support = models.BooleanField(default=False)
    dicomweb_qido_prefix = models.CharField(blank=True, max_length=2000)
    dicomweb_wado_prefix = models.CharField(blank=True, max_length=2000)
    dicomweb_stow_prefix = models.CharField(blank=True, max_length=2000)
    dicomweb_authorization_header = models.CharField(blank=True, max_length=2000)

    objects: DicomNodeManager["DicomServer"] = DicomNodeManager["DicomServer"]()


class DicomFolder(DicomNode):
    NODE_TYPE = DicomNode.NodeType.FOLDER

    path = models.CharField(max_length=256)
    quota = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="The disk quota of this folder in GB.",
    )
    warn_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="When to warn the admins by Email (used space in GB).",
    )

    objects: DicomNodeManager["DicomFolder"] = DicomNodeManager["DicomFolder"]()


class DicomJob(models.Model):
    class Status(models.TextChoices):
        UNVERIFIED = "UV", "Unverified"
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELING = "CI", "Canceling"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        WARNING = "WA", "Warning"
        FAILURE = "FA", "Failure"

    default_priority: int
    urgent_priority: int

    get_status_display: Callable[[], str]
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.UNVERIFIED)
    urgent = models.BooleanField(default=False)
    message = models.TextField(blank=True, default="")
    send_finished_mail = models.BooleanField(default=False)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_jobs",
    )
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    tasks: models.QuerySet["DicomTask"]

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["owner", "status"])]
        permissions = [
            (
                "can_process_urgently",
                "Can process urgently",
            )
        ]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"

    def get_absolute_url(self) -> str:
        # Gets overridden in subclasses
        ...

    def queue_pending_tasks(self):
        """Queues all pending tasks of this job."""
        assert self.status == DicomJob.Status.PENDING

        priority = self.default_priority
        if self.urgent:
            priority = self.urgent_priority

        for dicom_task in self.tasks.filter(status=DicomTask.Status.PENDING):
            assert dicom_task.queued_job is None

            model_label = get_model_label(dicom_task.__class__)
            queued_job_id = app.configure_task(
                "adit_server.core.tasks.process_dicom_task",
                allow_unknown=False,
                priority=priority,
            ).defer(model_label=model_label, task_id=dicom_task.pk)
            dicom_task.queued_job_id = queued_job_id
            dicom_task.save()

    def reset_tasks(self, only_failed=False) -> None:
        if only_failed:
            tasks = self.tasks.filter(status=DicomTask.Status.FAILURE)
        else:
            tasks = self.tasks.all()

        reset_tasks(tasks)

    def post_process(self, suppress_email=False) -> bool:
        """Evaluates all the tasks of a dicom job and sets the job state accordingly.

        Should be called whenever task are updated or manipulated.

        Returns:
            True if the job is finished, False otherwise
        """
        if self.tasks.filter(status=DicomTask.Status.PENDING).exists():
            if self.status != DicomJob.Status.CANCELING:
                self.status = DicomJob.Status.PENDING
                self.save()
            return False

        if self.tasks.filter(status=DicomTask.Status.IN_PROGRESS).exists():
            if self.status != DicomJob.Status.CANCELING:
                self.status = DicomJob.Status.IN_PROGRESS
                self.save()
            return False

        if self.status == DicomJob.Status.CANCELING:
            self.status = DicomJob.Status.CANCELED
            self.save()
            return False

        # Job is finished and we evaluate its final status
        has_success = self.tasks.filter(status=DicomTask.Status.SUCCESS).exists()
        has_warning = self.tasks.filter(status=DicomTask.Status.WARNING).exists()
        has_failure = self.tasks.filter(status=DicomTask.Status.FAILURE).exists()

        if has_success and not has_warning and not has_failure:
            self.status = DicomJob.Status.SUCCESS
            self.message = "All tasks succeeded."
        elif has_success and has_failure or has_warning and has_failure:
            self.status = DicomJob.Status.FAILURE
            self.message = "Some tasks failed."
        elif has_success and has_warning:
            self.status = DicomJob.Status.WARNING
            self.message = "Some tasks have warnings."
        elif has_warning:
            self.status = DicomJob.Status.WARNING
            self.message = "All tasks have warnings."
        elif has_failure:
            self.status = DicomJob.Status.FAILURE
            self.message = "All tasks failed."
        else:
            # at least one of success, warnings or failures must be > 0
            raise AssertionError(f"Invalid task status list of {self}.")

        self.end = timezone.now()
        self.save()

        if self.send_finished_mail and not suppress_email:
            send_job_finished_mail(self)

        return True

    @property
    def is_deletable(self) -> bool:
        non_pending_tasks = self.tasks.exclude(status=DicomTask.Status.PENDING)
        return (
            self.status in [self.Status.UNVERIFIED, self.Status.PENDING]
            and non_pending_tasks.count() == 0
        )

    @property
    def is_verified(self) -> bool:
        return self.status != self.Status.UNVERIFIED

    @property
    def is_cancelable(self) -> bool:
        return self.status in [self.Status.PENDING, self.Status.IN_PROGRESS]

    @property
    def is_resumable(self) -> bool:
        return self.status == self.Status.CANCELED

    @property
    def is_retriable(self) -> bool:
        return self.status == self.Status.FAILURE

    @property
    def is_restartable(self) -> bool:
        return self.status in [
            self.Status.CANCELED,
            self.Status.SUCCESS,
            self.Status.WARNING,
            self.Status.FAILURE,
        ]

    @property
    def processed_tasks(self) -> models.QuerySet["DicomTask"]:
        non_processed = (
            DicomTask.Status.PENDING,
            DicomTask.Status.IN_PROGRESS,
        )
        return self.tasks.exclude(status__in=non_processed)


class TransferJob(DicomJob):
    trial_protocol_id = models.CharField(
        blank=True, max_length=64, validators=[no_backslash_char_validator]
    )
    trial_protocol_name = models.CharField(
        blank=True, max_length=64, validators=[no_backslash_char_validator]
    )
    archive_password = models.CharField(blank=True, max_length=50)

    class Meta(DicomJob.Meta):
        abstract = True
        permissions = DicomJob.Meta.permissions + [
            (
                "can_transfer_unpseudonymized",
                "Can transfer unpseudonymized",
            )
        ]


class DicomTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        WARNING = "WA", "Warning"
        FAILURE = "FA", "Failure"

    job_id: int
    job = models.ForeignKey(DicomJob, on_delete=models.CASCADE, related_name="tasks")
    source_id: int
    source = models.ForeignKey(DicomNode, related_name="+", on_delete=models.PROTECT)
    queued_job_id: int
    queued_job = models.OneToOneField(
        ProcrastinateJob, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    get_status_display: Callable[[], str]
    status = models.CharField(
        max_length=2,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    message = models.TextField(blank=True, default="")
    log = models.TextField(blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"

    def get_absolute_url(self) -> str: ...

    def queue_pending_task(self) -> None:
        """Queues a dicom task."""
        assert self.status == DicomTask.Status.PENDING
        assert self.queued_job is None

        priority = self.job.default_priority
        if self.job.urgent:
            priority = self.job.urgent_priority

        model_label = get_model_label(self.__class__)
        queued_job_id = app.configure_task(
            "adit_server.core.tasks.process_dicom_task",
            allow_unknown=False,
            priority=priority,
        ).defer(model_label=model_label, task_id=self.pk)
        self.queued_job_id = queued_job_id
        self.save()

    @property
    def is_deletable(self) -> bool:
        return self.status == self.Status.PENDING

    @property
    def is_resettable(self) -> bool:
        return self.status in [
            self.Status.CANCELED,
            self.Status.SUCCESS,
            self.Status.WARNING,
            self.Status.FAILURE,
        ]

    @property
    def is_killable(self) -> bool:
        return self.status == self.Status.IN_PROGRESS


class TransferTask(DicomTask):
    job = models.ForeignKey(
        TransferJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    destination_id: int
    destination = models.ForeignKey(DicomNode, related_name="+", on_delete=models.PROTECT)
    patient_id = models.CharField(
        max_length=64,
        validators=[
            no_backslash_char_validator,
            no_control_chars_validator,
            no_wildcard_chars_validator,
        ],
    )
    study_uid = models.CharField(
        max_length=64,
        validators=[uid_chars_validator],
    )
    series_uids = ArrayField(
        models.CharField(max_length=64, validators=[uid_chars_validator]),
        blank=True,
        default=list,
    )
    pseudonym = models.CharField(
        blank=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )

    class Meta(DicomTask.Meta):
        abstract = True

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"
