from __future__ import absolute_import, unicode_literals

import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adit.settings.production")

app = Celery("adit")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


from celery.signals import setup_logging  # pylint: disable=wrong-import-position


@setup_logging.connect
def config_loggers(*args, **kwargs):  # pylint: disable=unused-argument
    from logging.config import dictConfig  # pylint: disable=import-outside-toplevel
    from django.conf import settings  # pylint: disable=import-outside-toplevel

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))
