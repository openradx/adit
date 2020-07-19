from django.db import models
from django.conf import settings
from django.urls import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from .site import job_type_choices, job_detail_views

class AppSettings(models.Model):
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'App settings'
    

class DicomNode(models.Model):

    class NodeType(models.TextChoices):
        SERVER = 'SV', 'Server'
        FOLDER = 'FO', 'Folder'

    node_name = models.CharField(unique=True, max_length=64)
    node_type = models.CharField(max_length=2, choices=NodeType.choices)

    def __str__(self):
        node_types_dict = {key: value for key, value in self.NodeType.choices}
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


class DicomFolder(DicomNode):
    path = models.CharField(max_length=256)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_type = DicomNode.NodeType.FOLDER


class DicomJob(models.Model):
    
    class Status(models.TextChoices):
        UNVERIFIED = 'UV', 'Unverified'
        PENDING =  'PE', 'Pending'
        IN_PROGRESS = 'IP', 'In Progress'
        PAUSED = 'PA', 'Paused'
        CANCELING = 'CI', 'Canceling'
        CANCELED = 'CA', 'Canceled'
        COMPLETED = 'CP', 'Completed'

    class Meta:
        indexes = [
            models.Index(fields=['created_by', 'status'])
        ]

    source = models.ForeignKey(DicomNode, related_name='+', null=True, on_delete=models.SET_NULL)
    destination = models.ForeignKey(DicomNode, related_name='+', null=True, on_delete=models.SET_NULL)
    job_type = models.CharField(max_length=2, choices=job_type_choices)
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.UNVERIFIED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
            related_name='jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    stopped_at = models.DateTimeField(null=True)

    def get_absolute_url(self):
        return reverse('dicom_job_detail', args=[str(self.id)])

    def is_deletable(self):
        return self.status in [
            self.Status.UNVERIFIED, 
            self.Status.PENDING
        ]

    def is_cancelable(self):
        return self.status in [
            self.Status.IN_PROGRESS,
            self.Status.PAUSED
        ]

    def __str__(self):
        status_dict = {key: value for key, value in self.Status.choices}
        return f"{self.__class__.__name__} {status_dict[self.status]}"