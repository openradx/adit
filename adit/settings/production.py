from .base import *  # noqa: F403
from .base import env

# Production settings, see
# https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

DEBUG = False

DATABASES["default"]["PASSWORD"] = env.str("POSTGRES_PASSWORD")  # noqa: F405

STATIC_ROOT = env.str("DJANGO_STATIC_ROOT")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_TIMEOUT = 60
email_config = env.email_url("DJANGO_EMAIL_URL")
EMAIL_HOST = email_config["EMAIL_HOST"]
EMAIL_PORT = email_config.get("EMAIL_PORT", 25)
EMAIL_HOST_USER = email_config.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = email_config.get("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = email_config.get("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = email_config.get("EMAIL_USE_SSL", False)
