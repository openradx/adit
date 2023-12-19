from django.db import models

from ...models import AppSettings, TransferJob, TransferTask


class ExampleAppSettings(AppSettings):
    pass


class ExampleTransferJob(TransferJob):
    default_priority = 5
    urgent_priority = 10

    def get_absolute_url(self):
        return "/"


class ExampleTransferTask(TransferTask):
    job = models.ForeignKey(ExampleTransferJob, on_delete=models.CASCADE, related_name="tasks")

    def get_absolute_url(self):
        return "/"
