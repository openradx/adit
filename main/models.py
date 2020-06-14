from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from .site import transfer_job_type_choices


class DicomNode(models.Model):

    class NodeType(models.TextChoices):
        SERVER = 'SV', 'Server'
        PATH = 'PA', 'Path'

    node_id = models.CharField(unique=True, max_length=64)
    node_name = models.CharField(max_length=128)
    node_type = models.CharField(max_length=2, choices=NodeType.choices)

    def __str__(self):
        node_types_dict = {key: value for key, value in self.NodeType.choices}
        return f"{self.node_name} ({node_types_dict[self.node_type]})"


class DicomServer(DicomNode):
    ae_title = models.CharField(unique=True, max_length=16)
    ip = models.GenericIPAddressField()
    port = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_type = DicomNode.NodeType.SERVER


class DicomPath(DicomNode):
    path = models.CharField(max_length=256)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_type = DicomNode.NodeType.PATH


class TransferJob(models.Model):
    
    class Status(models.TextChoices):
        PENDING =  'PE', 'Pending'
        IN_PROGRESS = 'PR', 'In Progress'
        CANCELED = 'CA', 'Canceled'
        COMPLETED = 'CP', 'Completed'

    source = models.ForeignKey(DicomNode, related_name='+', null=True, on_delete=models.SET_NULL)
    target = models.ForeignKey(DicomNode, related_name='+', null=True, on_delete=models.SET_NULL)
    job_type = models.CharField(max_length=2, choices=transfer_job_type_choices)
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    stopped_at = models.DateTimeField(null=True)

    def __str__(self):
        status_dict = {key: value for key, value in self.Status.choices}
        return f"Transfer Job - {status_dict[self.status]}"