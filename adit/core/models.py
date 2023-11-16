from typing import TYPE_CHECKING, Callable, Generic, Literal, TypeVar

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.constraints import UniqueConstraint

from adit.accounts.models import Institute, User

from .validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
    uid_chars_validator,
)

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class CoreSettings(models.Model):
    id: int
    maintenance_mode = models.BooleanField(default=False)
    announcement = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Core settings"

    def __str__(self):
        return f"{self.__class__.__name__} [ID {self.id}]"

    @classmethod
    def get(cls):
        return cls.objects.first()


class AppSettings(models.Model):
    id: int
    # Lock the creation of new jobs
    locked = models.BooleanField(default=False)
    # Suspend the background processing.
    suspended = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        return cls.objects.first()


TModel = TypeVar("TModel", bound=models.Model)


class DicomNodeManager(Generic[TModel], models.Manager[TModel]):
    def accessible_by_user(self, user: User, access_type: Literal["source", "destination"]):
        # Also staff users can only use nodes that are assigned to an institute (but they
        # must not be a member of that institute in contrast to normal users).
        if user.is_staff:
            accessible_nodes = self.all()
        else:
            accessible_nodes = self.filter(accesses__institute__in=user.institutes.all())

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

    id: int
    node_type = models.CharField(max_length=2, choices=NodeType.choices)
    name = models.CharField(unique=True, max_length=64)
    institutes = models.ManyToManyField(
        Institute,
        blank=True,
        related_name="dicom_nodes",
        through="DicomNodeInstituteAccess",
    )

    objects: DicomNodeManager["DicomNode"] = DicomNodeManager["DicomNode"]()

    class Meta:
        ordering = ("name",)

    def __str__(self):
        node_types_dict = dict(self.NodeType.choices)
        return f"DICOM {node_types_dict[self.node_type]} {self.name}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.node_type:
            if self.NODE_TYPE not in dict(self.NodeType.choices):
                raise AssertionError(f"Invalid node type: {self.NODE_TYPE}")
            self.node_type = self.NODE_TYPE

    def is_accessible_by_user(
        self, user: User, access_type: Literal["source", "destination"]
    ) -> bool:
        return DicomNode.objects.accessible_by_user(user, access_type).filter(id=self.id).exists()


class DicomNodeInstituteAccess(models.Model):
    id: int
    dicom_node = models.ForeignKey(DicomNode, on_delete=models.CASCADE, related_name="accesses")
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE)
    source = models.BooleanField(default=False)
    destination = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "DICOM node institute accesses"
        constraints = [
            UniqueConstraint(
                fields=["dicom_node", "institute"],
                name="unique_dicom_node_per_institute",
            )
        ]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [ID {self.id}]"


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

    if TYPE_CHECKING:
        tasks = RelatedManager["DicomTask"]()

    id: int
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

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["owner", "status"])]
        permissions = [
            (
                "can_process_urgently",
                "Can process urgently",
            )
        ]

    def __str__(self):
        return f"{self.__class__.__name__} [ID {self.id}]"

    def reset_tasks(self, only_failed=False):
        if only_failed:
            dicom_tasks = self.tasks.filter(status=DicomTask.Status.FAILURE)
        else:
            dicom_tasks = self.tasks.all()

        dicom_tasks.update(
            status=DicomJob.Status.PENDING,
            retries=0,
            message="",
            log="",
            start=None,
            end=None,
        )

    @property
    def is_deletable(self):
        non_pending_tasks = self.tasks.exclude(status=DicomTask.Status.PENDING)
        return (
            self.status in [self.Status.UNVERIFIED, self.Status.PENDING]
            and non_pending_tasks.count() == 0
        )

    @property
    def is_verified(self):
        return self.status != self.Status.UNVERIFIED

    @property
    def is_cancelable(self):
        return self.status in [self.Status.PENDING, self.Status.IN_PROGRESS]

    @property
    def is_resumable(self):
        return self.status == self.Status.CANCELED

    @property
    def is_retriable(self):
        return self.status == self.Status.FAILURE

    @property
    def is_restartable(self):
        return self.status in [
            self.Status.CANCELED,
            self.Status.SUCCESS,
            self.Status.WARNING,
            self.Status.FAILURE,
        ]

    @property
    def processed_tasks(self):
        non_processed = (
            DicomTask.Status.PENDING,
            DicomTask.Status.IN_PROGRESS,
        )
        return self.tasks.exclude(status__in=non_processed)


class TransferJob(DicomJob):
    class Meta(DicomJob.Meta):
        abstract = True
        permissions = DicomJob.Meta.permissions + [
            (
                "can_transfer_unpseudonymized",
                "Can transfer unpseudonymized",
            )
        ]

    trial_protocol_id = models.CharField(
        blank=True, max_length=64, validators=[no_backslash_char_validator]
    )
    trial_protocol_name = models.CharField(
        blank=True, max_length=64, validators=[no_backslash_char_validator]
    )
    archive_password = models.CharField(blank=True, max_length=50)


class QueuedTask(models.Model):
    id: int
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    priority = models.PositiveIntegerField()
    eta = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    locked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["content_type", "object_id"],
                name="unique_queued_task_per_dicom_task",
            )
        ]
        indexes = [
            models.Index(
                fields=["locked", "eta", "priority", "created"],
                name="fetch_next_task_idx",
            )
        ]

    def __str__(self):
        return f"{self.__class__.__name__} [{self.content_type} {self.object_id}]"


class DicomTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        WARNING = "WA", "Warning"
        FAILURE = "FA", "Failure"

    id: int
    job_id: int
    job = models.ForeignKey(DicomJob, on_delete=models.CASCADE, related_name="tasks")
    source_id: int
    source = models.ForeignKey(DicomNode, related_name="+", on_delete=models.PROTECT)
    get_status_display: Callable[[], str]
    status = models.CharField(
        max_length=2,
        choices=Status.choices,
        default=Status.PENDING,
    )
    retries = models.PositiveSmallIntegerField(default=0)
    message = models.TextField(blank=True, default="")
    log = models.TextField(blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    _queued = GenericRelation(QueuedTask)

    class Meta:
        abstract = True
        ordering = ("id",)

    def __str__(self):
        return f"{self.__class__.__name__} [Job ID {self.job.id}, Task ID {self.id}]"

    @property
    def queued(self) -> QueuedTask | None:
        return self._queued.first()


class TransferTask(DicomTask):
    class Meta(DicomTask.Meta):
        abstract = True

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

    def __str__(self):
        return (
            f"{self.__class__.__name__} "
            f"[Source {self.source}, "
            f"Destination {self.destination}, "
            f"Job ID {self.job.id}, Task ID {self.id}]"
        )
