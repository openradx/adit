from django.db import models
from main.models import TransferJob
from .apps import BATCH_TRANSFER_JOB_KEY


class BatchTransferJob(TransferJob):
    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_type = BATCH_TRANSFER_JOB_KEY


class BatchTransferRequest(models.Model):

    class Status(models.TextChoices):
        SUCCESS = 'SU', 'Success'
        WARNING = 'WA', 'Warning'
        ERROR = 'ER', 'Error'

    request_id = models.CharField(max_length=16)
    patient_id = models.CharField(null=True, max_length=64)
    patient_name = models.CharField(null=True, max_length=256)
    patient_birth_date = models.DateField()
    study_date = models.DateField()
    modality = models.CharField(max_length=16)
    pseudonym = models.CharField(null=True, max_length=256)
    status_code = models.CharField(null=True, max_length=2, choices=Status.choices)
    status_message = models.CharField(null=True, max_length=256)
    job = models.ForeignKey(BatchTransferJob, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('request_id', 'job'))
