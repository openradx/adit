from celery.schedules import crontab

from .base import *  # noqa: F403
from .base import env

# Production settings, see
# https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"  # noqa: F405

DATABASES["default"]["PASSWORD"] = env.str("POSTGRES_PASSWORD")  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_TIMEOUT = 60
EMAIL_HOST = env("DJANGO_EMAIL_HOST")
EMAIL_PORT = env("DJANGO_EMAIL_PORT")
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env("DJANGO_EMAIL_USE_TLS")

CELERY_BEAT_SCHEDULE["backup-db"] = {  # noqa: F405
    "task": "adit.core.tasks.backup_db",
    "schedule": crontab(minute=0, hour=3),  # execute daily at 3 o'clock UTC
}
