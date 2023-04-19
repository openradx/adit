from django.db import models
from adit.core.models import AppSettings, DicomJob, DicomTask, TransferJob, TransferTask
from adit.batch_transfer.models import BatchTransferJob
from adit.batch_transfer.tasks import ProcessBatchTransferJob

# Create your models here.
class UploadSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Upload settings"

class UploadJob(TransferJob):
    project_name = models.CharField(max_length=150)
    project_description = models.TextField(max_length=2000)

    def delay(self):
        current_app.send_task("adit.batch_transfer.tasks.ProcessBatchTransferJob", (self.id,))

    def get_absolute_url(self):
        return reverse("upload_job_create", args=[str(self.id)])

class UploadTask(TransferTask):
    job = models.ForeignKey(
        UploadJob,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    lines = models.JSONField(default=list)

    def get_absolute_url(self):
        return reverse("upload_task_detail", args=[self.job.id, self.task_id])