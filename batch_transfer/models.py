from django.db import models
from main.models import TransferJob

class BatchTransferRequest(models.Model):

    class Status(models.TextChoices):
        SUCCESS = 'SU', 'Success'
        WARNING = 'WA', 'Warning'
        ERROR = 'ER', 'Error'

    request_id=models.CharField(max_length=16)
    patient_id=models.CharField(null=True, max_length=64)
    patient_name=models.CharField(null=True, max_length=256)
    patient_birth_date=models.DateField()
    study_date=models.DateField()
    modality=models.CharField(max_length=16)
    pseudonym=models.CharField(null=True, max_length=256)
    status_code=models.CharField(null=True, max_length=2, choices=Status.choices)
    status_message=models.CharField(null=True, max_length=256)
    job=models.ForeignKey(TransferJob, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('request_id', 'job'))
