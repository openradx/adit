import subprocess
import traceback
from datetime import timedelta

import humanize
import redis
import sherlock
from celery import Task as CeleryTask
from celery import shared_task
from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore
from celery.exceptions import Retry
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command
from django.utils import timezone
from sherlock import Lock

from adit.accounts.models import User

from .errors import DicomConnectionError, OutOfDiskSpaceError
from .models import AppSettings, DicomFolder, DicomJob, DicomTask
from .utils.mail import (
    send_job_finished_mail,
    send_mail_to_admins,
)
from .utils.scheduler import Scheduler
from .utils.task_utils import update_job_status

logger = get_task_logger(__name__)

sherlock.configure(backend=sherlock.backends.REDIS)
sherlock.configure(client=redis.Redis.from_url(settings.REDIS_URL))


@shared_task
def broadcast_mail(subject: str, message: str):
    recipients = []
    for user in User.objects.all():
        if user.email:
            recipients.append(user.email)

    send_mail(subject, message, settings.SUPPORT_EMAIL, recipients)

    logger.info("Successfully sent an Email to %d recipents.", len(recipients))


@shared_task
def check_disk_space():
    # TODO: Maybe only check active folders (that belong to an institute and are active
    # as a destination)
    folders = DicomFolder.objects.all()
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


@shared_task
def backup_db():
    call_command("dbbackup", "--clean", "-v 2")


class ProcessDicomJob(CeleryTask):
    dicom_job_class: type[DicomJob]
    default_priority: int
    urgent_priority: int
    process_dicom_task: CeleryTask

    def run(self, dicom_job_id: int):
        dicom_job = self.dicom_job_class.objects.get(id=dicom_job_id)

        logger.info("%s started.", dicom_job)

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

    def run(self, task_id: int):
        dicom_task = self.dicom_task_class.objects.get(id=task_id)

        try:
            status, message = self.process_dicom_task(dicom_task)
            dicom_task.status = status
            dicom_task.message = message
        except Retry as err:
            # When the task is rescheduled a Retry will be raised that must be
            # passed through to Celery.
            raise err
        except (DicomConnectionError, OutOfDiskSpaceError) as err:
            # Inside the handle_dicom_task errors of kind RetriableTaskError can be raised
            # which are handled here and also raise a Retry in the end.
            logger.exception("Retriable error occurred during %s.", dicom_task)

            # We can't use the Celery built-in max_retries and celery_task.request.retries
            # directly as we also use celery_task.retry() for scheduling tasks.
            if dicom_task.retries < settings.DICOM_TASK_RETRIES:
                delta = (
                    timedelta(hours=24)
                    if isinstance(err, OutOfDiskSpaceError)
                    else timedelta(minutes=15)
                )
                logger.info("Retrying task in %s.", humanize.naturaldelta(delta))

                dicom_task.status = DicomTask.Status.PENDING
                dicom_task.message = "Task timed out and will be retried."
                if dicom_task.log:
                    dicom_task.log += "\n"
                dicom_task.log += str(err)

                dicom_task.retries += 1

                # Increase the priority slightly to make sure images that were moved
                # from the GE archive storage to the fast access storage are still there
                # when we retry.
                priority = self.request.delivery_info["priority"]
                if priority < settings.CELERY_TASK_QUEUE_MAX_PRIORITY:
                    priority += 1

                raise self.retry(eta=timezone.now() + delta, exc=err, priority=priority)

            logger.error("No more retries for finally failed %s: %s", dicom_task, str(err))

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
        except ValueError as err:
            # We raise ValueError for expected errors
            logger.exception("Error during %s.", dicom_task)

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
            if dicom_task.log:
                dicom_task.log += "\n---\n"
            dicom_task.log += traceback.format_exc()
        except Exception as err:
            # Unexpected errors are handled here
            logger.exception("Unexpected error during %s.", dicom_task)

            dicom_task.status = DicomTask.Status.FAILURE
            dicom_task.message = str(err)
            if dicom_task.log:
                dicom_task.log += "\n-----\n"
            dicom_task.log += traceback.format_exc()
        finally:
            dicom_task.end = timezone.now()
            dicom_task.save()

            logger.info("%s ended.", dicom_task)

            dicom_job = dicom_task.job

            with Lock("update_job_after_task"):
                dicom_job.refresh_from_db()
                update_job_status(dicom_job)
                dicom_job.end = timezone.now()
                dicom_job.save()

            if dicom_job.send_finished_mail:
                send_job_finished_mail(dicom_job)

            logger.info("%s ended.", dicom_job)

    def process_dicom_task(self, dicom_task: DicomTask) -> tuple[DicomTask.Status, str]:
        logger.info("%s started.", dicom_task)

        dicom_job = dicom_task.job

        # Dicom jobs are canceled by the DicomJobCancelView and tasks are also revoked there,
        # but it could happen that the task was already picked up by a worker. We then just
        # ignore that task.
        if (
            dicom_job.status == DicomJob.Status.CANCELING
            or dicom_task.status == DicomTask.Status.CANCELED
        ):
            return (DicomTask.Status.CANCELED, "Task was canceled.")

        if dicom_task.status != dicom_task.Status.PENDING:
            raise AssertionError(f"Invalid {dicom_task} status: {dicom_task.get_status_display()}")

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

        # When the first DICOM task is really processed then the status of the DICOM
        # job switches from PENDING to IN_PROGRESS
        # TODO: Maybe it would be nicer if the job is only IN_PROGRESS as long as a
        # DICOM task is currently IN_PROGRESS (cave, must be handled in a distributed lock)
        if dicom_job.status == DicomJob.Status.PENDING:
            dicom_job.status = DicomJob.Status.IN_PROGRESS
            dicom_job.start = timezone.now()
            dicom_job.save()

        dicom_task.status = DicomTask.Status.IN_PROGRESS
        dicom_task.start = timezone.now()
        dicom_task.save()

        return self.handle_dicom_task(dicom_task)

    def handle_dicom_task(self, dicom_task) -> tuple[DicomTask.Status, str]:
        """Does the actual work of the dicom task.

        Should return a tuple of the final status of that task and a message that is
        stored in the task model.
        """
        raise NotImplementedError("Subclasses must implement this method.")
