from datetime import timedelta
from celery import Task as CeleryTask
from django.utils import timezone
from ..models import AppSettings, DicomJob, DicomTask
from ..utils.scheduler import Scheduler


def precheck_job(dicom_job: DicomJob):
    if dicom_job.status != DicomJob.Status.PENDING:
        raise AssertionError(
            f"Invalid {dicom_job} status: {dicom_job.get_status_display()}"
        )


def precheck_task(dicom_task: DicomTask):
    if dicom_task.status != DicomTask.Status.PENDING:
        raise AssertionError(
            f"Invalid {dicom_task} status: {dicom_task.get_status_display()}"
        )


def check_canceled(dicom_job: DicomJob, dicom_task: DicomTask):
    if dicom_job.status == DicomJob.Status.CANCELING:
        dicom_task.status = DicomTask.Status.CANCELED
        dicom_task.end = timezone.now()
        dicom_task.save()
        return dicom_task.status
    return None


def check_can_run_now(
    celery_task: CeleryTask,
    app_settings: AppSettings,
    dicom_job: DicomJob,
    dicom_task: DicomTask,
):
    if not dicom_job.urgent:
        scheduler = Scheduler(
            app_settings.slot_begin_time,
            app_settings.slot_end_time,
        )
        if scheduler.must_be_scheduled():
            raise celery_task.retry(
                eta=scheduler.next_slot(),
                exc=Warning(f"Outside of time slot. Rescheduling {dicom_task}"),
            )

    if app_settings.suspended:
        raise celery_task.retry(
            eta=timezone.now() + timedelta(minutes=60),
            exc=Warning(f"App suspended. Rescheduling {dicom_task}."),
        )


# TODO
def prepare_dicom_task(task_class, settings_class, logger):
    def _decorator(func):
        def _wrapper(celery_task, dicom_task_id):
            dicom_task = task_class.objects.get(id=dicom_task_id)
            dicom_job = dicom_task.job

            logger.info(
                "Processing selective transfer task [Job ID %d, Task ID %d].",
                dicom_job.id,
                dicom_task.id,
            )

            precheck_task(dicom_task)

            canceled_status = check_canceled(dicom_job, dicom_task)
            if canceled_status:
                return canceled_status

            check_can_run_now(celery_task, settings_class.get(), dicom_job, dicom_task)

            if dicom_job.status == DicomJob.Status.PENDING:
                dicom_job.status = DicomJob.Status.IN_PROGRESS
                dicom_job.start = timezone.now()
                dicom_job.save()

            func(dicom_task)

        return _wrapper

    return _decorator
