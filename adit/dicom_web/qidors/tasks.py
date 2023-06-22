from django.conf import settings

from adit.celery import app as celery_app
from adit.core.tasks import (
    HandleFailedDicomJob,
    HandleFinishedDicomJob,
    ProcessDicomJob,
    ProcessDicomTask,
)

from .models import (
    DicomQidoJob,
    DicomQidoSettings,
    DicomQidoTask,
)
from .utils import execute_qido


class ProcessDicomQidoTask(ProcessDicomTask):
    dicom_task_class = DicomQidoTask
    app_settings_class = DicomQidoSettings

    def handle_dicom_task(self, dicom_task):
        return execute_qido(dicom_task, self)


process_dicom_qido_task = ProcessDicomQidoTask()
celery_app.register_task(process_dicom_qido_task)


class HandleFinishedDicomQidoJob(HandleFinishedDicomJob):
    dicom_job_class = DicomQidoJob
    send_job_finished_mail = False


handle_finished_dicom_qido_job = HandleFinishedDicomQidoJob()
celery_app.register_task(handle_finished_dicom_qido_job)


class HandleFailedDicomQidoJob(HandleFailedDicomJob):
    dicom_job_class = DicomQidoJob
    send_job_failed_mail = False


handle_failed_dicom_qido_job = HandleFailedDicomQidoJob()
celery_app.register_task(handle_failed_dicom_qido_job)


class ProcessDicomQidoJob(ProcessDicomJob):
    dicom_job_class = DicomQidoJob
    default_priority = settings.QIDO_DEFAULT_PRIORITY
    urgent_priority = settings.QIDO_URGENT_PRIORITY
    process_dicom_task = process_dicom_qido_task
    handle_failed_dicom_job = handle_failed_dicom_qido_job
    handle_finished_dicom_job = handle_finished_dicom_qido_job


process_dicom_qido_job = ProcessDicomQidoJob()
celery_app.register_task(process_dicom_qido_job)
