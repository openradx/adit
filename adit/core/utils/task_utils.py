from logging import Logger
from typing import Type, List, Callable
from functools import wraps
from datetime import date, timedelta
import redis
from celery import Task as CeleryTask
from django.conf import settings
from django.utils import timezone
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.redis_lru import redis_lru
from adit.core.utils.mail import send_job_failed_mail
from ..models import AppSettings, DicomJob, DicomTask
from ..utils.scheduler import Scheduler


def prepare_dicom_job(dicom_job_class: Type[DicomJob], logger: Logger):
    def _decorator(func: Callable):
        @wraps(func)
        def _wrapper(dicom_job_id):
            dicom_job = dicom_job_class.objects.get(id=dicom_job_id)

            logger.info("Processing %s.", dicom_job)

            if dicom_job.status != DicomJob.Status.PENDING:
                raise AssertionError(
                    f"Invalid {dicom_job} status: {dicom_job.get_status_display()}"
                )

            func(dicom_job)

        return _wrapper

    return _decorator


def prepare_dicom_task(
    task_class: Type[DicomTask], settings_class: Type[AppSettings], logger: Logger
):
    def _decorator(func: Callable):
        @wraps(func)
        def _wrapper(celery_task: CeleryTask, dicom_task_id: int):
            dicom_task = task_class.objects.get(id=dicom_task_id)
            dicom_job = dicom_task.job

            logger.info("Processing %s.", dicom_task)

            if dicom_task.status != DicomTask.Status.PENDING:
                raise AssertionError(
                    f"Invalid {dicom_task} status: {dicom_task.get_status_display()}"
                )

            if dicom_job.status == DicomJob.Status.CANCELING:
                dicom_task.status = DicomTask.Status.CANCELED
                dicom_task.end = timezone.now()
                dicom_task.save()
                return dicom_task.status

            app_settings = settings_class.get()

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

            if dicom_job.status == DicomJob.Status.PENDING:
                dicom_job.status = DicomJob.Status.IN_PROGRESS
                dicom_job.start = timezone.now()
                dicom_job.save()

            return func(dicom_task)

        return _wrapper

    return _decorator


def finish_dicom_job(dicom_job_class: Type[DicomJob], logger: Logger):
    def _decorator(func: Callable):
        @wraps(func)
        def _wrapper(dicom_task_status_list: List[str], job_id: int):
            dicom_job = dicom_job_class.objects.get(id=job_id)

            logger.info("%s finished.", dicom_job)

            if (
                dicom_job.status == DicomJob.Status.CANCELING
                and DicomJob.Status.CANCELED in dicom_task_status_list
            ):
                dicom_job.status = DicomJob.Status.CANCELED
                dicom_job.save()
                return

            has_success = False
            has_failure = False
            for status in dicom_task_status_list:
                if status == DicomTask.Status.SUCCESS:
                    has_success = True
                elif status == DicomTask.Status.FAILURE:
                    has_failure = True
                else:
                    raise AssertionError(
                        f"Invalid dicom task result status in {dicom_job}: {status}"
                    )

            if has_success and has_failure:
                dicom_job.status = DicomJob.Status.WARNING
                dicom_job.message = "Some transfer tasks failed."
            elif has_success:
                dicom_job.status = DicomJob.Status.SUCCESS
                dicom_job.message = "All transfer tasks succeeded."
            elif has_failure:
                dicom_job.status = DicomJob.Status.FAILURE
                dicom_job.message = "All transfer tasks failed."
            else:
                raise AssertionError(
                    f"At least one task of {dicom_job} must succeed or fail."
                )

            dicom_job.save()

            func(dicom_job)

        return _wrapper

    return _decorator


def handle_job_failure(dicom_job_class: Type[DicomJob], logger: Logger):
    def _decorator(func: Callable):
        # The Celery documentation is wrong about the provided parameters and when
        # the callback is called. This function definition seems to work however.
        # See https://github.com/celery/celery/issues/3709
        @wraps(func)
        def _wrapper(*args, **kwargs):
            celery_task_id = args[0]
            job_id = kwargs["job_id"]

            dicom_job = dicom_job_class.objects.get(id=job_id)

            logger.error("%s failed unexpectedly.", dicom_job)

            dicom_job.status = DicomJob.Status.FAILURE
            dicom_job.message = "Failed unexpectedly."
            dicom_job.save()

            send_job_failed_mail(dicom_job, celery_task_id)

            func(dicom_job)

        return _wrapper

    return _decorator


@redis_lru(capacity=10000, slicer=slice(3))
def fetch_patient_id_cached(
    connector: DicomConnector, patient_id: str, patient_name: str, birth_date: date
):
    """Fetch the patient for this request.

    Raises an error if there is no patient or there are multiple patients for this request.
    """
    patients = connector.find_patients(
        {
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": birth_date,
        }
    )

    if len(patients) == 0:
        raise ValueError("No patients found.")
    if len(patients) > 1:
        raise ValueError("Multiple patients found.")

    return patients[0]["PatientID"]


fetch_patient_id_cached.init(redis.Redis.from_url(settings.REDIS_URL))
