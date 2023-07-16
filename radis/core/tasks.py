import subprocess
import traceback

import redis
import sherlock
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from sherlock import Lock

from radis.accounts.models import User
from radis.core.utils.report_utils import Report

from .utils.mail import (
    send_mail_to_admins,
)

logger = get_task_logger(__name__)

# TODO: delete, and maybe also remove sherlock from toml
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
    # TODO: check disk space of vespa volume
    # folders = DicomFolder.objects.filter(destination_active=True)
    # for folder in folders:
    #     size = int(subprocess.check_output(["du", "-sm", folder.path]).split()[0].decode("utf-8"))
    #     size = size / 1024  # convert MB to GB
    #     if folder.warn_size is not None and size > folder.warn_size:
    #         quota = "?"
    #         if folder.quota is not None:
    #             quota = folder.quota
    #         msg = (
    #             f"Low disk space of destination folder: {folder.name}\n"
    #             f"{size} GB of {quota} GB used."
    #         )
    #         logger.warning(msg)
    #         send_mail_to_admins("Warning, low disk space!", msg)
    pass


@shared_task(ignore_result=True)
def process_report(**kwargs):
    # TODO: send to vespa
    report = Report(**kwargs)
