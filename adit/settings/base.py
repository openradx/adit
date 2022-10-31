"""
Django settings for adit project.

Generated by 'django-admin startproject' using Django 3.0.7.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

from pathlib import Path
import environ
import toml
from celery.schedules import crontab

env = environ.Env()

# The base directory of the project (the root of the repository)
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent

# Read pyproject.toml file
pyproject = toml.load(BASE_DIR / "pyproject.toml")

ADIT_VERSION = pyproject["tool"]["poetry"]["version"]

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

BASE_URL = env.str("BASE_URL", default="")

SITE_ID = 1

ADIT_FULLSTACK = env.bool("ADIT_FULLSTACK", default=False)

# Used by our custom migration adit.core.migrations.0002_UPDATE_SITE_NAME
# to set the domain and name of the sites framework
ADIT_SITE_DOMAIN = env.str("ADIT_SITE_DOMAIN", default="adit.org")
ADIT_SITE_NAME = env.str("ADIT_SITE_NAME", default="adit.org")

INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",
    "adit.accounts.apps.AccountsConfig",
    "registration",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "revproxy",
    "loginas",
    "crispy_forms",
    "django_tables2",
    "rest_framework",
    "adit.core.apps.CoreConfig",
    "adit.api.apps.ApiConfig",
    "adit.selective_transfer.apps.SelectiveTransferConfig",
    "adit.batch_query.apps.BatchQueryConfig",
    "adit.batch_transfer.apps.BatchTransferConfig",
    "adit.dicom_explorer.apps.DicomExplorerConfig",
    "channels",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "adit.core.middlewares.MaintenanceMiddleware",
    "adit.core.middlewares.TimezoneMiddleware",
]

ROOT_URLCONF = "adit.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "adit.core.site.base_context_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "adit.wsgi.application"

# env.db() loads the DB setup from the DATABASE_URL environment variable using
# Django-environ.
# The sqlite database is still used for pytest tests.
DATABASES = {"default": env.db(default="sqlite:///./adit-sqlite.db")}

# Django 3.2 switched to BigAutoField for primary keys. It must be set explicitly
# and requires a migration.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

SYSLOG_HOST = env.str("SYSLOG_HOST", default="localhost")
SYSLOG_PORT = env.int("SYSLOG_PORT", default=514)

# See following examples:
# https://github.com/django/django/blob/master/django/utils/log.py
# https://cheat.readthedocs.io/en/latest/django/logging.html
# https://stackoverflow.com/a/7045981/166229
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "simple": {
            "format": "[%(asctime)s] %(name)-12s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S %Z",
        },
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S %Z",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "syslog": {
            "level": "INFO",
            "class": "logging.handlers.SysLogHandler",
            "address": (SYSLOG_HOST, SYSLOG_PORT),
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "CRITICAL",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "adit": {
            "handlers": ["console", "syslog", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "syslog", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console", "syslog"],
            "level": "WARNING",
            "propagate": False,
        },
        "pydicom": {
            "handlers": ["console", "syslog"],
            "level": "WARNING",
            "propagate": False,
        },
        "pynetdicom": {
            "handlers": ["console", "syslog"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {"handlers": ["console", "syslog"], "level": "ERROR"},
}

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "de-de"

# We don't want to have German translations, but everything in English
USE_I18N = False

# But we still want to have dates and times localized
USE_L10N = True

USE_TZ = True

TIME_ZONE = "UTC"

# All REST API requests must come from authenticated clients
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ]
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATICFILES_DIRS = (BASE_DIR / "adit" / "static",)

STATIC_URL = "/static/"

STATIC_ROOT = env.str("DJANGO_STATIC_ROOT", default=(BASE_DIR / "staticfiles"))

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Where to redirect to after login
LOGIN_REDIRECT_URL = "home"

# For crispy forms
CRISPY_TEMPLATE_PACK = "bootstrap4"

# This seems to be imporant for development on Gitpod as CookieStorage
# and FallbackStorage does not work there.
# Seems to be the same problem with Cloud9 https://stackoverflow.com/a/34828308/166229
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

EMAIL_SUBJECT_PREFIX = "[ADIT] "

# An Email address used by the ADIT server to notify about finished jobs and
# management notifications.
SERVER_EMAIL = env.str("DJANGO_SERVER_EMAIL", default="support@adit.test")
DEFAULT_FROM_EMAIL = SERVER_EMAIL

# A support Email address that is presented to the users where
# they can get support.
SUPPORT_EMAIL = env.str("SUPPORT_EMAIL", default=SERVER_EMAIL)

# Also used by django-registration-redux to send account approval emails
admin_first_name = env.str("ADMIN_FIRST_NAME", default="ADIT")
admin_last_name = env.str("ADMIN_LAST_NAME", default="Admin")
admin_full_name = admin_first_name + " " + admin_last_name
ADMINS = [
    (
        admin_full_name,
        env.str("ADMIN_EMAIL", default="admin@adit.test"),
    )
]

# Settings for django-registration-redux
REGISTRATION_FORM = "adit.accounts.forms.RegistrationForm"
ACCOUNT_ACTIVATION_DAYS = 14
REGISTRATION_OPEN = True

# Channels
ASGI_APPLICATION = "adit.asgi.application"

# RabbitMQ is used as Celery message broker and to send incoming images
# from the receiver to the workers.
RABBITMQ_URL = env.str("RABBITMQ_URL", default="amqp://localhost")

# Rabbit Management console is integrated in ADIT by using an reverse
# proxy (django-revproxy).This allows to use the authentication of ADIT.
# But as RabbitMQ authentication can't be disabled we have to login
# there with "guest" as username and password again.
RABBIT_MANAGEMENT_HOST = env.str("RABBIT_MANAGEMENT_HOST", default="localhost")
RABBIT_MANAGEMENT_PORT = env.int("RABBIT_MANAGEMENT_PORT", default=15672)

# Redis is used as Celery result backend and as LRU cache for patient IDs.
REDIS_URL = env.str("REDIS_URL", default="redis://localhost:6379/0")

# Celery
# see https://github.com/celery/celery/issues/5026 for how to name configs
if USE_TZ:
    CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = RABBITMQ_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_TASK_DEFAULT_QUEUE = "default_queue"
CELERY_TASK_ROUTES = {
    "adit.selective_transfer.tasks.ProcessSelectiveTransferTask": {
        "queue": "dicom_task_queue",
    },
    "adit.batch_query.tasks.ProcessBatchQueryTask": {
        "queue": "dicom_task_queue",
    },
    "adit.batch_transfer.tasks.ProcessBatchTransferTask": {
        "queue": "dicom_task_queue",
    },
}
CELERY_BEAT_SCHEDULE = {
    "check-disk-space": {
        "task": "adit.core.tasks.check_disk_space",
        "schedule": crontab(minute=0, hour=7),  # execute daily at 7 o'clock UTC
    }
}

# Max retries is normally 3. We have to overwrite this, see
# https://github.com/celery/celery/issues/976
# Retries happen when a DICOM server is not responding, a requested
# study is currently offline, the scheduler is rescheduling (because
# we are outside the time slot). So we have to set this quite high.
# None would turn it off, but we make sure that no bug let retry it
# forever.
CELERY_TASK_ANNOTATIONS = {"*": {"max_retries": 100}}

# For priority queues, see also apply_async calls in the models.
# Requires RabbitMQ as the message broker!
CELERY_TASK_QUEUE_MAX_PRIORITY = 10
CELERY_TASK_DEFAULT_PRIORITY = 5

# Only non prefetched tasks can be sorted by their priority. So we only
# prefetch only one task at a time.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Not sure if this is really necessary for priorities to work, but saw this mentioned
# https://medium.com/better-programming/python-celery-best-practices-ae182730bb81
# https://stackoverflow.com/a/47980598/166229
CELERY_TASK_ACKS_LATE = True

# Flower is integrated in ADIT by using a reverse proxy (django-revproxy).
# This allows to use the authentication of ADIT.
FLOWER_HOST = env.str("FLOWER_HOST", default="localhost")
FLOWER_PORT = env.int("FLOWER_PORT", default=5555)

# Orthanc servers are integrated in ADIT by using a reverse proxy (django-revproxy).
ORTHANC1_HOST = env.str("ORTHANC1_HOST", default="localhost")
ORTHANC1_HTTP_PORT = env.int("ORTHANC1_HTTP_PORT", default=6501)
ORTHANC1_DICOM_PORT = env.int("ORTHANC1_HTTP_PORT", default=7501)
ORTHANC2_HOST = env.str("ORTHANC2_HOST", default="localhost")
ORTHANC2_HTTP_PORT = env.int("ORTHANC2_HTTP_PORT", default=6502)
ORTHANC2_DICOM_PORT = env.int("ORTHANC2_HTTP_PORT", default=7502)

# For django-filter
FILTERS_EMPTY_CHOICE_LABEL = "Show All"

###
# ADIT specific settings
###

# General ADIT settings
ADIT_AE_TITLE = env.str("ADIT_AE_TITLE", default="ADIT1")

# The delimiter in CSV batch files
CSV_DELIMITER = ";"

# Usually a transfer job must be verified by an admin. By setting
# this option to True ADIT will schedule unverified transfers
# (and directly set the status of the job to PENDING).
SELECTIVE_TRANSFER_UNVERIFIED = True
BATCH_QUERY_UNVERIFIED = True
BATCH_TRANSFER_UNVERIFIED = True

# A timezone that is used for users of the web interface.
USER_TIME_ZONE = env.str("USER_TIME_ZONE", default=None)

# Celery / RabbitMQ queue priorities of transfer jobs
SELECTIVE_TRANSFER_DEFAULT_PRIORITY = 3
SELECTIVE_TRANSFER_URGENT_PRIORITY = 7
BATCH_TRANSFER_DEFAULT_PRIORITY = 2
BATCH_TRANSFER_URGENT_PRIORITY = 6
BATCH_QUERY_DEFAULT_PRIORITY = 4
BATCH_QUERY_URGENT_PRIORITY = 8

# The maximum number of resulting studies for selective_transfer query
SELECTIVE_TRANSFER_RESULT_LIMIT = 101

# The maximum number of results (patients or studies) in dicom_explorer
DICOM_EXPLORER_RESULT_LIMIT = 101

# The timeout in dicom_explorer a DICOM server must respond
DICOM_EXPLORER_RESPONSE_TIMEOUT = 3  # seconds

# The timeout we wait for images of a C-MOVE download
C_MOVE_DOWNLOAD_TIMEOUT = 60  # seconds

# Show DICOM debug messages of pynetdicom
DICOM_DEBUG_LOGGER = False

# How often to retry a failed transfer task before the task is definitively failed
TRANSFER_TASK_RETRIES = 2

# The maximum number of batch queries a normal user can process in one job
# (staff user are not limited)
MAX_BATCH_QUERY_SIZE = 1000

# The maximum number of batch transfers a normal user can process in one job
# (staff users are not limited)
MAX_BATCH_TRANSFER_SIZE = 500

# Exclude modalities when listing studies and during queries or transfers
EXCLUDE_MODALITIES = ["PR", "SR"]

# If an ethics committee approval is required for batch transfer
ETHICS_COMMITTEE_APPROVAL_REQUIRED = True
