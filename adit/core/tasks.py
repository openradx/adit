import subprocess

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command

from adit.accounts.models import User

from .models import DicomFolder
from .utils.mail import send_mail_to_admins

logger = get_task_logger(__name__)


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
