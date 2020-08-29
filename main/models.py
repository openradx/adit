from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from .site import job_type_choices
from .utils.dicom_connector import DicomConnector
from .fields import SeparatedValuesField


class AppSettings(models.Model):
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "App settings"


class DicomNode(models.Model):
    class NodeType(models.TextChoices):
        SERVER = "SV", "Server"
        FOLDER = "FO", "Folder"

    node_name = models.CharField(unique=True, max_length=64)
    node_type = models.CharField(max_length=2, choices=NodeType.choices)

    def __str__(self):
        node_types_dict = dict(self.NodeType.choices)
        return f"DICOM {node_types_dict[self.node_type]} {self.node_name}"


class DicomServer(DicomNode):
    ae_title = models.CharField(unique=True, max_length=16)
    ip = models.GenericIPAddressField()
    port = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    patient_root_query_model_find = models.BooleanField(default=True)
    patient_root_query_model_get = models.BooleanField(default=True)
    patient_root_query_model_move = models.BooleanField(default=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_type = DicomNode.NodeType.SERVER

    def create_connector(self, auto_connect=True):
        return DicomConnector(
            DicomConnector.Config(
                client_ae_title=settings.ADIT_AE_TITLE,
                server_ae_title=self.ae_title,
                server_ip=self.ip,
                server_port=self.port,
                patient_root_query_model_find=self.patient_root_query_model_find,
                patient_root_query_model_get=self.patient_root_query_model_get,
                patient_root_query_model_move=self.patient_root_query_model_move,
                auto_connect=auto_connect,
            )
        )


class DicomFolder(DicomNode):
    path = models.CharField(max_length=256)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_type = DicomNode.NodeType.FOLDER


class TransferJob(models.Model):
    class Status(models.TextChoices):
        UNVERIFIED = "UV", "Unverified"
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELING = "CI", "Canceling"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        WARNING = "WA", "Warning"
        FAILURE = "FA", "Failure"

    class Meta:
        indexes = [models.Index(fields=["created_by", "status"])]

    source = models.ForeignKey(
        DicomNode, related_name="+", null=True, on_delete=models.SET_NULL
    )
    destination = models.ForeignKey(
        DicomNode, related_name="+", null=True, on_delete=models.SET_NULL
    )
    job_type = models.CharField(max_length=2, choices=job_type_choices)
    status = models.CharField(
        max_length=2, choices=Status.choices, default=Status.UNVERIFIED
    )
    message = models.TextField(blank=True, null=True)
    trial_protocol_id = models.CharField(max_length=64, blank=True, null=True)
    trial_protocol_name = models.CharField(max_length=64, blank=True, null=True)
    archive_password = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transfer_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    stopped_at = models.DateTimeField(null=True)

    def get_absolute_url(self):
        return reverse("transfer_job_detail", args=[str(self.id)])

    def get_processed_tasks(self):
        non_processed = (TransferTask.Status.PENDING, TransferTask.Status.IN_PROGRESS)
        return self.tasks.exclude(status__in=non_processed)

    def is_deletable(self):
        return self.status in [self.Status.UNVERIFIED, self.Status.PENDING]

    def is_cancelable(self):
        return self.status in (self.Status.IN_PROGRESS,)

    def is_transfer_to_archive(self):
        return bool(self.archive_password)

    def __str__(self):
        status_dict = dict(self.Status.choices)
        return f"{self.__class__.__name__} {status_dict[self.status]}"


class TransferTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "PE", "Pending"
        IN_PROGRESS = "IP", "In Progress"
        CANCELED = "CA", "Canceled"
        SUCCESS = "SU", "Success"
        FAILURE = "FA", "Failure"

    # The generic relation is optional and may be used to organize
    # the transfers in an additional way
    content_type = models.ForeignKey(
        ContentType, blank=True, null=True, on_delete=models.SET_NULL
    )
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    job = models.ForeignKey(TransferJob, on_delete=models.CASCADE, related_name="tasks")
    patient_id = models.CharField(max_length=64)
    study_uid = models.CharField(max_length=64)
    series_uids = SeparatedValuesField(blank=True, null=True)
    pseudonym = models.CharField(max_length=324, blank=True, null=True)
    status = models.CharField(
        max_length=2, choices=Status.choices, default=Status.PENDING,
    )
    message = models.TextField(blank=True, null=True)
    log = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    stopped_at = models.DateTimeField(null=True)
