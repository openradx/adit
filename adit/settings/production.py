from .base import *  # noqa: F403
from .base import env

# Production settings, see
# https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

DEBUG = False

ENVIRONMENT = "production"

DATABASES["default"]["PASSWORD"] = env.str("POSTGRES_PASSWORD")  # noqa: F405

STATIC_ROOT = env.str("DJANGO_STATIC_ROOT")

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)

email_config = env.dj_email_url("DJANGO_EMAIL_URL")
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": email_config["EMAIL_HOST"],
            "port": email_config.get("EMAIL_PORT", 25),
            "username": email_config.get("EMAIL_HOST_USER"),
            "password": email_config.get("EMAIL_HOST_PASSWORD"),
            "use_tls": email_config.get("EMAIL_USE_TLS", False),
            "use_ssl": email_config.get("EMAIL_USE_SSL", False),
            "timeout": 60,
        },
    },
}
