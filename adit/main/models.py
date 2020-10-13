from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from model_utils.managers import InheritanceManager
from .utils.dicom_connector import DicomConnector
from .fields import SeparatedValuesField, InheritanceForeignKey


class AppSettings(models.Model):
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "App settings"


class DicomNode(models.Model):
    name = models.CharField(unique=True, max_length=64)
    active = models.BooleanField(default=True)
    objects = InheritanceManager()

    def __str__(self):
        return f"{self.__class__.__name__} {self.name}"


class DicomServer(DicomNode):
    ae_title = models.CharField(unique=True, max_length=16)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    patient_root_find_support = models.BooleanField(default=True)
    patient_root_get_support = models.BooleanField(default=True)
    patient_root_move_support = models.BooleanField(default=True)
    study_root_find_support = models.BooleanField(default=True)
    study_root_get_support = models.BooleanField(default=True)
    study_root_move_support = models.BooleanField(default=True)

    def create_connector(self, auto_connect=True):
        return DicomConnector(
            DicomConnector.Config(
                client_ae_title=settings.ADIT_AE_TITLE,
                server_ae_title=self.ae_title,
                server_host=self.host,
                server_port=self.port,
                patient_root_find_support=self.patient_root_find_support,
                patient_root_get_support=self.patient_root_get_support,
                patient_root_move_support=self.patient_root_move_support,
                study_root_find_support=self.study_root_find_support,
                study_root_get_support=self.study_root_get_support,
                study_root_move_support=self.study_root_move_support,
                auto_connect=auto_connect,
            )
        )

    def __str__(self):
        return f"DICOM Server {self.name}"


class DicomFolder(DicomNode):
    path = models.CharField(max_length=256)


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
        indexes = [models.Index(fields=["owner", "status"])]

    source = InheritanceForeignKey(
        DicomNode, related_name="+", on_delete=models.PROTECT
    )
    destination = InheritanceForeignKey(
        DicomNode, related_name="+", on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=2, choices=Status.choices, default=Status.UNVERIFIED
    )
    message = models.TextField(blank=True, null=True)
    trial_protocol_id = models.CharField(null=True, blank=True, max_length=64)
    trial_protocol_name = models.CharField(null=True, blank=True, max_length=64)
    archive_password = models.CharField(null=True, blank=True, max_length=50)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transfer_jobs"
    )
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    objects = InheritanceManager()

    def job_type(self):
        return self._meta.verbose_name

    def get_processed_tasks(self):
        non_processed = (TransferTask.Status.PENDING, TransferTask.Status.IN_PROGRESS)
        return self.tasks.exclude(status__in=non_processed)

    def is_deletable(self):
        return self.status in (self.Status.UNVERIFIED, self.Status.PENDING)

    def is_cancelable(self):
        return self.status in (self.Status.IN_PROGRESS,)

    def is_unverified(self):
        return self.status == self.Status.UNVERIFIED

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
    series_uids = SeparatedValuesField(null=True, blank=True)
    pseudonym = models.CharField(null=True, blank=True, max_length=64)
    status = models.CharField(
        max_length=2,
        choices=Status.choices,
        default=Status.PENDING,
    )
    message = models.TextField(null=True, blank=True)
    log = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
