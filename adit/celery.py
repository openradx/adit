from __future__ import absolute_import, unicode_literals

import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adit.settings.development")

app = Celery("adit")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# If priority queues do not work this might be another option, see
# https://stackoverflow.com/a/47980598/166229
# app.conf.task_queue_max_priority = 10

from celery.signals import setup_logging  # noqa: E402


# When setting up logging like this then CELERY_WORKER_HIJACK_ROOT_LOGGER
# has no effect anymore as it Celery will never try to hijack it.abs
# It will be forced to take the logger configuration from our Django
# settings. The downside is that we don't get the Celery logger
# (get_task_logger) anymore that prints out the Celery task ID with
# the log message.
@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
