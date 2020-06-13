from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

class DicomNode(models.Model):

    class NodeType(models.TextChoices):
        SERVER = 'SV', 'Server'
        PATH = 'PA', 'Path'

    nodeId = models.CharField(max_length=64)
    nodeName = models.CharField(max_length=128)
    nodeType = models.CharField(max_length=2, choices=NodeType.choices)

class DicomServer(DicomNode):
    ae_title = models.CharField(unique=True, max_length=16)
    ip = models.GenericIPAddressField()
    port = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)])

class DicomPath(DicomNode):
    path = models.CharField(max_length=256)

class TransferJob(models.Model):
    
    class Status(models.TextChoices):
        PENDING =  'PE', 'Pending'
        IN_PROGRESS = 'PR', 'In Progress'
        CANCELED = 'CA', 'Canceled'
        COMPLETED = 'CP', 'Completed'

    source = models.ForeignKey(DicomNode, related_name='+', null=True, on_delete=models.SET_NULL)
    target = models.ForeignKey(DicomNode, related_name='+', null=True, on_delete=models.SET_NULL)
    jobType = models.CharField(max_length=16)
    status = models.CharField(max_length=2, choices=Status.choices)
    created_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True)
    stopped_at = models.DateTimeField(null=True)