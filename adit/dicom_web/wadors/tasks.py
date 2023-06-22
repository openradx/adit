from django.conf import settings

from adit.celery import app as celery_app
from adit.core.tasks import (
    HandleFailedDicomJob,
    HandleFinishedDicomJob,
    ProcessDicomJob,
    ProcessDicomTask,
)

from .models import (
    DicomWadoJob,
    DicomWadoSettings,
    DicomWadoTask,
)
from .utils import execute_wado


# Wado
class ProcessDicomWadoTask(ProcessDicomTask):
    dicom_task_class = DicomWadoTask
    app_settings_class = DicomWadoSettings

    def handle_dicom_task(self, dicom_task):
        return execute_wado(dicom_task, self)


process_dicom_wado_task = ProcessDicomWadoTask()
celery_app.register_task(process_dicom_wado_task)


class HandleFinishedDicomWadoJob(HandleFinishedDicomJob):
    dicom_job_class = DicomWadoJob
    send_job_finished_mail = False


handle_finished_dicom_wado_job = HandleFinishedDicomWadoJob()
celery_app.register_task(handle_finished_dicom_wado_job)


class HandleFailedDicomWadoJob(HandleFailedDicomJob):
    dicom_job_class = DicomWadoJob
    send_job_failed_mail = False


handle_failed_dicom_wado_job = HandleFailedDicomWadoJob()
celery_app.register_task(handle_failed_dicom_wado_job)


class ProcessDicomWadoJob(ProcessDicomJob):
    dicom_job_class = DicomWadoJob
    default_priority = settings.WADO_DEFAULT_PRIORITY
    urgent_priority = settings.WADO_URGENT_PRIORITY
    process_dicom_task = process_dicom_wado_task
    handle_failed_dicom_job = handle_failed_dicom_wado_job
    handle_finished_dicom_job = handle_finished_dicom_wado_job


process_dicom_wado_job = ProcessDicomWadoJob()
celery_app.register_task(process_dicom_wado_job)
