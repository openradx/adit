"""
Django settings for adit project.

Generated by 'django-admin startproject' using Django 3.0.7.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

from pathlib import Path
from typing import Literal

from environs import env
from pydicom import config as pydicom_config

# During development and calling `manage.py` from the host we have to load the .env file manually.
# Some env variables will still need a default value, as those are only set in the compose file.
if not env.bool("IS_DOCKER_CONTAINER", default=False):
    env.read_env()

# The base directory of the project (the root of the repository)
BASE_PATH = Path(__file__).resolve(strict=True).parent.parent.parent

# The source paths of the project
SOURCE_PATHS = [BASE_PATH / "adit"]

# Fetch version from the environment which is passed through from the git version tag
PROJECT_VERSION = env.str("PROJECT_VERSION", default="v0.0.0")

# The project URL used in the navbar and footer
PROJECT_URL = "https://github.com/openradx/adit"

# Needed by sites framework
SITE_ID = 1

# The following settings are synced to the Site model of the sites framework on startup
# (see common/apps.py in adit-radis-shared).
SITE_DOMAIN = env.str("SITE_DOMAIN")
SITE_NAME = env.str("SITE_NAME")

SECRET_KEY = env.str("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "daphne",
    "whitenoise.runserver_nostatic",
    "adit_radis_shared.common.apps.CommonConfig",
    "registration",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "django.contrib.postgres",
    "django_extensions",
    "procrastinate.contrib.django",
    "dbbackup",
    "revproxy",
    "loginas",
    "django_cotton.apps.SimpleAppConfig",
    "block_fragments.apps.SimpleAppConfig",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_htmx",
    "django_tables2",
    "rest_framework",
    "adrf",
    "adit.core.apps.CoreConfig",
    "adit_radis_shared.accounts.apps.AccountsConfig",
    "adit_radis_shared.token_authentication.apps.TokenAuthenticationConfig",
    "adit.selective_transfer.apps.SelectiveTransferConfig",
    "adit.batch_query.apps.BatchQueryConfig",
    "adit.batch_transfer.apps.BatchTransferConfig",
    "adit.dicom_explorer.apps.DicomExplorerConfig",
    "adit.dicom_web.apps.DicomWebConfig",
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
    "django_htmx.middleware.HtmxMiddleware",
    "adit_radis_shared.accounts.middlewares.ActiveGroupMiddleware",
    "adit_radis_shared.common.middlewares.MaintenanceMiddleware",
]

ROOT_URLCONF = "adit.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "OPTIONS": {
            "loaders": [
                (
                    "block_fragments.loader.Loader",
                    [
                        (
                            "django.template.loaders.cached.Loader",
                            [
                                "django_cotton.cotton_loader.Loader",
                                "django.template.loaders.filesystem.Loader",
                                "django.template.loaders.app_directories.Loader",
                            ],
                        )
                    ],
                )
            ],
            "builtins": [
                "django_cotton.templatetags.cotton",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "adit_radis_shared.common.site.base_context_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "adit.wsgi.application"

ASGI_APPLICATION = "adit.asgi.application"

# This seems to be important for Cloud IDEs as CookieStorage does not work there.
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# DATABASE_URL is only set in the compose file. For local development on the host
# we use the port from the .env file directly.
postgres_dev_port = env.int("POSTGRES_DEV_PORT", default=5432)
database_url = f"postgres://postgres:postgres@localhost:{postgres_dev_port}/postgres"
DATABASES = {"default": env.dj_db_url("DATABASE_URL", default=database_url)}

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL = "accounts.User"

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

# A custom authentication backend that supports a single currently active group.
AUTHENTICATION_BACKENDS = ["adit_radis_shared.accounts.backends.ActiveGroupModelBackend"]

# Where to redirect to after login
LOGIN_REDIRECT_URL = "home"

# Settings for django-registration-redux
REGISTRATION_FORM = "adit_radis_shared.accounts.forms.RegistrationForm"
ACCOUNT_ACTIVATION_DAYS = 14
REGISTRATION_OPEN = True

EMAIL_SUBJECT_PREFIX = "[ADIT] "

# The email address critical error messages of the server will be sent from.
SERVER_EMAIL = env.str("DJANGO_SERVER_EMAIL")

# The Email address is also used to notify about finished jobs and management notifications.
DEFAULT_FROM_EMAIL = SERVER_EMAIL

# A support Email address that is presented to the users where they can get support.
SUPPORT_EMAIL = env.str("SUPPORT_EMAIL")

# Also used by django-registration-redux to send account approval emails
ADMINS = [(env.str("DJANGO_ADMIN_FULL_NAME"), env.str("DJANGO_ADMIN_EMAIL"))]

# All REST API requests must come from authenticated clients
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "adit_radis_shared.token_authentication.auth.RestTokenAuthentication",
    ],
    "EXCEPTION_HANDLER": "adit.dicom_web.exceptions.dicom_web_exception_handler",
}

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
        "mail_admins": {
            "level": "CRITICAL",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "adit": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "pydicom": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "pynetdicom": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {"handlers": ["console"], "level": "ERROR"},
}

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

# TODO: We don't want use translations yet, but everything is hardcoded in English
USE_I18N = False

USE_TZ = True

TIME_ZONE = env.str("TIME_ZONE", default="UTC")

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/
STATIC_URL = "/static/"

# Additional (project wide) static files
STATICFILES_DIRS = (BASE_PATH / "adit" / "static",)

# For crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# django-templates2
DJANGO_TABLES2_TEMPLATE = "common/_django_tables2.html"

# The salt that is used for hashing new tokens in the token authentication app.
# Cave, changing the salt after some tokens were already generated makes them all invalid!
TOKEN_AUTHENTICATION_SALT = env.str("TOKEN_AUTHENTICATION_SALT")

# django-dbbackup
DBBACKUP_STORAGE = "django.core.files.storage.FileSystemStorage"
DBBACKUP_STORAGE_OPTIONS = {
    "location": env.str("DBBACKUP_STORAGE_LOCATION", default="/tmp/backups-adit")
}
DBBACKUP_CLEANUP_KEEP = 30

# Orthanc servers are integrated in ADIT by using a reverse proxy (django-revproxy).
ORTHANC1_HOST = env.str("ORTHANC1_HOST", default="localhost")
ORTHANC1_HTTP_PORT = env.int("ORTHANC1_HTTP_PORT", default=6501)
ORTHANC1_DICOM_PORT = env.int("ORTHANC1_DICOM_PORT", default=7501)
ORTHANC1_DICOMWEB_ROOT = env.str("ORTHANC1_DICOMWEB_ROOT", "dicom-web")
ORTHANC2_HOST = env.str("ORTHANC2_HOST", default="localhost")
ORTHANC2_HTTP_PORT = env.int("ORTHANC2_HTTP_PORT", default=6502)
ORTHANC2_DICOM_PORT = env.int("ORTHANC2_DICOM_PORT", default=7502)
ORTHANC2_DICOMWEB_ROOT = env.str("ORTHANC2_DICOMWEB_ROOT", "dicom-web")

# Used by django-filter
FILTERS_EMPTY_CHOICE_LABEL = "Show All"

# Global pydicom settings
pydicom_config.convert_wrong_length_to_UN = True

# The calling AE title of ADIT.
CALLING_AE_TITLE = env.str("CALLING_AE_TITLE")

# The AE title where the receiver is listening for incoming files.
RECEIVER_AE_TITLE = env.str("RECEIVER_AE_TITLE")

# The address and port of the STORE SCP server (part of the receiver).
# By default the STORE SCP server listens to all interfaces (empty string)
STORE_SCP_HOST = env.str("STORE_SCP_HOST", "localhost")
STORE_SCP_PORT = env.int("STORE_SCP_PORT", 11112)

# The address and port of the file transmit socket server (part of the receiver)
# that is used to transfer DICOM files from the receiver to the workers (when
# the PACS server does not support C-GET).
# By default the file transmit socket server listens to all interfaces (should
# not be a problem as it is inside the docker network).
FILE_TRANSMIT_HOST = env.str("FILE_TRANSMIT_HOST", "localhost")
FILE_TRANSMIT_PORT = env.int("FILE_TRANSMIT_PORT", 14638)

# Usually a transfer job must be verified by an admin. By setting
# this option to True ADIT will schedule unverified transfers
# (and directly set the status of the job to PENDING).
START_SELECTIVE_TRANSFER_UNVERIFIED = True
START_BATCH_QUERY_UNVERIFIED = True
START_BATCH_TRANSFER_UNVERIFIED = True

# Priorities of dicom tasks
# Selective transfers have the highest priority as those are
# normally fewer than the other tasks. Batch transfers have the lowest
# priority as there are mostly numerous and long running.
SELECTIVE_TRANSFER_DEFAULT_PRIORITY = 4
SELECTIVE_TRANSFER_URGENT_PRIORITY = 8
BATCH_TRANSFER_DEFAULT_PRIORITY = 2
BATCH_TRANSFER_URGENT_PRIORITY = 6
BATCH_QUERY_DEFAULT_PRIORITY = 3
BATCH_QUERY_URGENT_PRIORITY = 7

# The priority for stalled jobs that are retried.
STALLED_JOBS_RETRY_PRIORITY = 10

# The used archive type when creating a new archive in selective transfer.
# .7z is more the secure as the names of files and folder can't be viewed
# (in contrast to .zip), but .zip is more widely used.
SELECTIVE_TRANSFER_ARCHIVE_TYPE: Literal["7z", "zip"] = "zip"

# The maximum number of resulting studies for selective_transfer query
SELECTIVE_TRANSFER_RESULT_LIMIT = 101

# The maximum number of results (patients or studies) in dicom_explorer
DICOM_EXPLORER_RESULT_LIMIT = 101

# The timeout in dicom_explorer a DICOM server must respond
DICOM_EXPLORER_RESPONSE_TIMEOUT = 3  # seconds

# The timeout we wait for images of a C-MOVE download
C_MOVE_DOWNLOAD_TIMEOUT = 30  # seconds

# Show DICOM debug messages of pynetdicom
ENABLE_DICOM_DEBUG_LOGGER = False

# How often to retry a failed dicom task before it is definitively failed
DICOM_TASK_MAX_ATTEMPTS = 3

# How long to wait in seconds before retrying a failed dicom task (exponential backoff)
DICOM_TASK_EXPONENTIAL_WAIT = 10  # 10 seconds

# How long to wait in seconds before killing a dicom task that is not finished yet
DICOM_TASK_PROCESS_TIMEOUT = 60 * 20  # 20 minutes

# How often to check the database if the DICOM task should be canceled
DICOM_TASK_CANCELED_MONITOR_INTERVAL = 10  # 10 seconds

# The maximum number of batch queries a normal user can process in one job
# (staff user are not limited)
MAX_BATCH_QUERY_SIZE = 1000

# The maximum number of batch transfers a normal user can process in one job
# (staff users are not limited)
MAX_BATCH_TRANSFER_SIZE = 500

# See example.env
EXCLUDE_MODALITIES = env.list("EXCLUDE_MODALITIES", default=[])

# If an ethics committee approval is required for batch transfer
ETHICS_COMMITTEE_APPROVAL_REQUIRED = True

# DicomWeb Settings
DEFAULT_BOUNDARY = "adit-boundary"
ERROR_MESSAGE = "Processing your DicomWeb request failed."

# If enabled, series are placed into separate folders when downloading a study.
# Otherwise all images of the whole study are placed into folder.
CREATE_SERIES_SUB_FOLDERS = True

# Elements to keep during pseudonymization
SKIP_ELEMENTS_ANONYMIZATION = [
    "AcquisitionDate",
    "AcquisitionDateTime",
    "AcquisitionTime",
    "ContentDate",
    "ContentTime",
    "SeriesDate",
    "SeriesTime",
    "StudyDate",
    "StudyTime",
]
