import celery
from adit.celery import app as celery_app
from celery import shared_task, Task as CeleryTask, chord
from celery.utils.log import get_task_logger

from django.conf import settings

from .models import (
    DicomWebQIDOJob,
    DicomWebQIDOTask,
    DicomWebQIDOSettings,
)

from adit.core.tasks import (
    ProcessDicomTask,
    ProcessDicomJob,
    HandleFinishedDicomJob,
    HandleFailedDicomJob,
)

from .utils.qido_utils import execute_qido

class ProcessDicomWebQIDOTask(CeleryTask):
    dicom_task_class = DicomWebQIDOTask
    app_settings_class = DicomWebQIDOSettings

    def handle_dicom_task(self, dicom_task):
        return execute_qido(dicom_task)

process_dicom_web_qido_task = ProcessDicomWebQIDOTask()
celery_app.register_task(process_dicom_web_qido_task)


class HandleFinishedDicomWebQIDOJob(HandleFinishedDicomJob):
    dicom_job_class = DicomWebQIDOJob
    send_job_finished_mail = False

handle_finished_dicom_web_qido_job = HandleFinishedDicomWebQIDOJob()
celery_app.register_task(handle_finished_dicom_web_qido_job)


class HandleFailedDicomWebQidoJob(HandleFailedDicomJob):
    dicom_job_class = DicomWebQIDOJob
    send_job_failed_mail = False

handle_failed_dicom_web_qido_job = HandleFailedDicomWebQidoJob
celery_app.register_task(handle_failed_dicom_web_qido_job)


class ProcessDicomWebQIDOJob(ProcessDicomJob):
    dicom_job_class = DicomWebQIDOJob
    default_priority = settings.QIDO_DEFAULT_PRIORITY
    urgent_priority = settings.QIDO_URGENT_PRIORITY
    process_dicom_task = process_dicom_web_qido_task
    handle_failed_dicom_job = handle_failed_dicom_web_qido_job
    handle_finished_dicom_job = handle_finished_dicom_web_qido_job

process_dicom_web_qido_job = ProcessDicomWebQIDOJob()
celery_app.register_task(process_dicom_web_qido_job)

