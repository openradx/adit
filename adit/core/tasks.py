import subprocess
from datetime import timedelta
from typing import List, Type
from celery import Task as CeleryTask
from celery import chord, shared_task
from celery.contrib.abortable import AbortableTask as AbortableCeleryTask
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.template.defaultfilters import pluralize
from django.utils import timezone
from ..accounts.models import User
from .models import AppSettings, DicomFolder, DicomJob, DicomTask
from .utils.mail import (
    send_job_failed_mail,
    send_job_finished_mail,
    send_mail_to_admins,
)
from .utils.scheduler import Scheduler

logger = get_task_logger(__name__)


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

    dicom_job_class: Type[DicomJob] = None
    default_priority: int = None
    urgent_priority: int = None
    process_dicom_task: CeleryTask = None
    handle_finished_dicom_job: CeleryTask = None
    handle_failed_dicom_job: CeleryTask = None

    def run(self, dicom_job_id: str):
        dicom_job = self.dicom_job_class.objects.get(id=dicom_job_id)

        logger.info("Proccessing %s.", dicom_job)

        if dicom_job.status != DicomJob.Status.PENDING:
            raise AssertionError(f"Invalid {dicom_job} status: {dicom_job.get_status_display()}")

        priority = self.default_priority
        if dicom_job.urgent:
            priority = self.urgent_priority

        pending_dicom_tasks = dicom_job.tasks.filter(status=DicomTask.Status.PENDING)

        process_dicom_tasks = [
            self.process_dicom_task.s(dicom_task.id).set(priority=priority)
            for dicom_task in pending_dicom_tasks
        ]

        result = chord(process_dicom_tasks)(
            self.handle_finished_dicom_job.s(dicom_job.id).on_error(
                self.handle_failed_dicom_job.s(job_id=dicom_job.id)
            )
        )

        # Save Celery task IDs to dicom tasks (for revoking them later if necessary)
        # Only works in when not in eager mode (used to debug Celery stuff)
        if not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            for query_task, celery_task in zip(pending_dicom_tasks, result.parent.results):
                query_task.celery_task_id = celery_task.id
                query_task.save()


class ProcessDicomTask(AbortableCeleryTask):
    dicom_task_class: Type[DicomTask] = None
    app_settings_class: Type[AppSettings] = None

    def run(self, dicom_task_id: int):
        dicom_task = self.dicom_task_class.objects.get(id=dicom_task_id)

        logger.info("Processing %s.", dicom_task)

        if dicom_task.status not in [
            DicomTask.Status.PENDING,
            DicomTask.Status.CANCELED,
        ]:
            raise AssertionError(f"Invalid {dicom_task} status: {dicom_task.get_status_display()}")

        # Dicom tasks are canceled by the DicomJobCancelView and are also revoked there.
        # But it could happen that the task was already fetched by a worker. We then just
        # ignore that task.
        if dicom_task.status == DicomTask.Status.CANCELED:
            return DicomTask.Status.CANCELED

        dicom_job = dicom_task.job

        app_settings = self.app_settings_class.get()

        if not dicom_job.urgent:
            scheduler = Scheduler(
                app_settings.slot_begin_time,
                app_settings.slot_end_time,
            )
            if scheduler.must_be_scheduled():
                raise self.retry(
                    eta=scheduler.next_slot(),
                    exc=Warning(f"Outside of time slot. Rescheduling {dicom_task}"),
                )

        if app_settings.suspended:
            raise self.retry(
                eta=timezone.now() + timedelta(minutes=60),
                exc=Warning(f"App suspended. Rescheduling {dicom_task}."),
            )

        if dicom_job.status == DicomJob.Status.PENDING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
            dicom_job.start = timezone.now()
            dicom_job.save()

        return self.handle_dicom_task(dicom_task)

    def handle_dicom_task(self, dicom_task):
        raise NotImplementedError("Subclasses must implement this method.")


class HandleFinishedDicomJob(CeleryTask):
    dicom_job_class: Type[DicomJob] = None
    send_job_finished_mail: bool = None

    def run(self, dicom_task_status_list: List[str], dicom_job_id: int):
        dicom_job = self.dicom_job_class.objects.get(id=dicom_job_id)

        logger.info("%s finished.", dicom_job)

        # When no celery task had to be revoked when canceling the job then the normal
        # callback is called in we end here (see also handle_job_failure).
        if dicom_job.status == DicomJob.Status.CANCELING:
            dicom_job.status = DicomJob.Status.CANCELED
            count = dicom_job.tasks.filter(status=DicomTask.Status.CANCELED).count()
            dicom_job.message = f"{count} task{pluralize(count)} canceled."
            dicom_job.save()
            return

        successes = 0
        warnings = 0
        failures = 0
        for status in dicom_task_status_list:
            if status == DicomTask.Status.SUCCESS:
                successes += 1
            elif status == DicomTask.Status.WARNING:
                warnings += 1
            elif status == DicomTask.Status.FAILURE:
                failures += 1
            else:
                raise AssertionError(f"Invalid dicom task result status in {dicom_job}: {status}")

        if successes and not warnings and not failures:
            dicom_job.status = DicomJob.Status.SUCCESS
            dicom_job.message = "All tasks succeeded."
        elif successes and failures or warnings and failures:
            dicom_job.status = DicomJob.Status.WARNING
            dicom_job.message = "Some tasks failed."
        elif successes and warnings:
            dicom_job.status = DicomJob.Status.WARNING
            dicom_job.message = "Some tasks with warnings."
        elif warnings:
            dicom_job.status = DicomJob.Status.WARNING
            dicom_job.message = "All tasks with warnings."
        elif failures:
            dicom_job.status = DicomJob.Status.FAILURE
            dicom_job.message = "All tasks failed."
        else:
            # at least one of success, warnings or failures must be > 0
            raise AssertionError(f"Invalid task status list of {dicom_job}.")

        dicom_job.save()

        if self.send_job_finished_mail:
            send_job_finished_mail(dicom_job)


class HandleFailedDicomJob(CeleryTask):
    dicom_job_class: Type[DicomJob] = None
    send_job_failed_mail: bool = None

    def run(self, *args, **kwargs):
        # The Celery documentation is wrong about the provided parameters and when
        # the callback is called. This function definition seems to work however.
        # See https://github.com/celery/celery/issues/3709
        celery_task_id = args[0]
        dicom_job = self.dicom_job_class.objects.get(id=kwargs["job_id"])

        logger.error("%s failed.", dicom_job)

        # When the job was canceled and celery tasks were revoked then
        # the on_error callback of the chord is called and we have to
        # handle the cancel here.
        if dicom_job.status == DicomJob.Status.CANCELING:
            dicom_job.status = DicomJob.Status.CANCELED
            count = dicom_job.tasks.filter(status=DicomTask.Status.CANCELED).count()
            dicom_job.message = f"{count} task{pluralize(count)} canceled."
            dicom_job.save()
            return

        dicom_job.status = DicomJob.Status.FAILURE
        dicom_job.message = "Job failed unexpectedly."
        dicom_job.save()

        if self.send_job_failed_mail:
            send_job_failed_mail(dicom_job, celery_task_id)
