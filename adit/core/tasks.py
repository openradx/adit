import subprocess
from datetime import timedelta

import redis
import sherlock
from celery import Task as CeleryTask
from celery import shared_task
from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from sherlock import Lock

from ..accounts.models import User
from .models import AppSettings, DicomFolder, DicomJob, DicomTask
from .utils.mail import (
    send_job_finished_mail,
    send_mail_to_admins,
)
from .utils.scheduler import Scheduler

logger = get_task_logger(__name__)

sherlock.configure(backend=sherlock.backends.REDIS)
sherlock.configure(client=redis.Redis.from_url(settings.REDIS_URL))


@shared_task(ignore_result=True)
def broadcast_mail(subject: str, message: str):
    recipients = []
    for user in User.objects.all():
        if user.email:
            recipients.append(user.email)

    send_mail(subject, message, settings.SUPPORT_EMAIL, recipients)

    logger.info("Successfully sent an Email to %d recipents.", len(recipients))


@shared_task(ignore_result=True)
def check_disk_space():
    folders = DicomFolder.objects.filter(destination_active=True)
    for folder in folders:
        size = int(subprocess.check_output(["du", "-sm", folder.path]).split()[0].decode("utf-8"))
        size = size / 1024  # convert MB to GB
        if folder.warn_size is not None and size > folder.warn_size:
            quota = "?"
            if folder.quota is not None:
                quota = folder.quota
            msg = (
                f"Low disk space of destination folder: {folder.name}\n"
                f"{size} GB of {quota} GB used."
            )
            logger.warning(msg)
            send_mail_to_admins("Warning, low disk space!", msg)


class ProcessDicomJob(CeleryTask):
    ignore_result = True

    dicom_job_class: type[DicomJob]
    default_priority: int
    urgent_priority: int
    process_dicom_task: CeleryTask

    def run(self, dicom_job_id: int):
        dicom_job = self.dicom_job_class.objects.get(id=dicom_job_id)

        logger.info("Proccessing %s.", dicom_job)

        if dicom_job.status != DicomJob.Status.PENDING:
            raise AssertionError(f"Invalid {dicom_job} status: {dicom_job.get_status_display()}")

        priority = self.default_priority
        if dicom_job.urgent:
            # Tasks of an urgent job get a higher priority
            priority = self.urgent_priority

        pending_dicom_tasks = dicom_job.tasks.filter(status=DicomTask.Status.PENDING)

        for dicom_task in pending_dicom_tasks:
            result = self.process_dicom_task.s(dicom_task.id).set(priority=priority).delay()

            # Save Celery task IDs to dicom tasks (for revoking them later if necessary)
            # Only works when not in eager mode (which is used to debug Celery stuff)
            if not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                dicom_task.celery_task_id = result.id
                dicom_task.save()


class ProcessDicomTask(AbortableCeleryTask):
    dicom_task_class: type[DicomTask]
    app_settings_class: type[AppSettings]

    def run(self, dicom_task_id: int):
        dicom_task = self.dicom_task_class.objects.get(id=dicom_task_id)

        try:
            self.process_task(dicom_task)
        finally:
            with Lock("update_job_after"):
                self.update_job_after(dicom_task.job)

        return dicom_task.status

    def process_task(self, dicom_task: DicomTask):
        logger.info("Processing %s.", dicom_task)

        if dicom_task.status not in [
            DicomTask.Status.PENDING,
            DicomTask.Status.CANCELED,
        ]:
            raise AssertionError(f"Invalid {dicom_task} status: {dicom_task.get_status_display()}")

        dicom_job = dicom_task.job

        # Dicom jobs are canceled by the DicomJobCancelView and tasks are also revoked there,
        # but it could happen that the task was already picked up by a worker. We then just
        # ignore that task.
        if (
            dicom_job.status == DicomJob.Status.CANCELING
            or dicom_task.status == DicomTask.Status.CANCELED
        ):
            return DicomTask.Status.CANCELED

        app_settings = self.app_settings_class.get()
        assert app_settings

        if not dicom_job.urgent:
            scheduler = Scheduler(
                app_settings.slot_begin_time,
                app_settings.slot_end_time,
            )
            if scheduler.must_be_scheduled():
                # TODO: Use Celery beat one_off tasks
                raise self.retry(
                    eta=scheduler.next_slot(),
                    exc=Warning(f"Outside of time slot. Rescheduling {dicom_task}"),
                )

        if app_settings.suspended:
            # TODO: Use Celery beat one_off tasks
            raise self.retry(
                eta=timezone.now() + timedelta(minutes=60),
                exc=Warning(f"App suspended. Rescheduling {dicom_task}."),
            )

        if dicom_job.status == DicomJob.Status.PENDING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
            dicom_job.start = timezone.now()
            dicom_job.save()

        self.handle_dicom_task(dicom_task)

    # TODO: Call after task finished (and status of task is already updated). It should also be
    # called in an distributed lock to prevent race conditions between multiple workers.
    def update_job_after(self, dicom_job: DicomJob, job_finished_mail: bool = True):
        """Evaluates all the tasks of a dicom job and sets the job status accordingly."""

        if dicom_job.status == DicomJob.Status.CANCELING:
            if not dicom_job.tasks.filter(status=DicomTask.Status.IN_PROGRESS).exists():
                dicom_job.status = DicomJob.Status.CANCELED
                dicom_job.save()
        elif dicom_job.tasks.filter(status=DicomTask.Status.IN_PROGRESS).exists():
            dicom_job.status = DicomJob.Status.IN_PROGRESS
            dicom_job.save()
        elif dicom_job.tasks.filter(status=DicomTask.Status.PENDING).exists():
            dicom_job.status = DicomJob.Status.PENDING
            dicom_job.save()
        else:
            has_success = dicom_job.tasks.filter(status=DicomTask.Status.SUCCESS).exists()
            has_warning = dicom_job.tasks.filter(status=DicomTask.Status.WARNING).exists()
            has_failure = dicom_job.tasks.filter(status=DicomTask.Status.FAILURE).exists()

            if has_success and not has_warning and not has_failure:
                dicom_job.status = DicomJob.Status.SUCCESS
                dicom_job.message = "All tasks succeeded."
            elif has_success and has_failure or has_warning and has_failure:
                dicom_job.status = DicomJob.Status.WARNING
                dicom_job.message = "Some tasks failed."
            elif has_success and has_warning:
                dicom_job.status = DicomJob.Status.WARNING
                dicom_job.message = "Some tasks have warnings."
            elif has_warning:
                dicom_job.status = DicomJob.Status.WARNING
                dicom_job.message = "All tasks have warnings."
            elif has_failure:
                dicom_job.status = DicomJob.Status.FAILURE
                dicom_job.message = "All tasks failed."
            else:
                # at least one of success, warnings or failures must be > 0
                raise AssertionError(f"Invalid task status list of {dicom_job}.")

            dicom_job.end = timezone.now()
            dicom_job.save()

            logger.info("%s finished.", dicom_job)

            if job_finished_mail:
                send_job_finished_mail(dicom_job)

    def handle_dicom_task(self, dicom_task):
        """Does the actual work of the dicom task.

        Should also update the status of the dicom task (on start and end) and should also
        set start and end datetime.
        """
        raise NotImplementedError("Subclasses must implement this method.")
