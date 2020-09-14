from .base import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .base import env

# Production settings, see
# https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_TIMEOUT = 60
EMAIL_HOST = env.str("DJANGO_EMAIL_HOST", default="outlook.office365.com")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=25)
EMAIL_HOST_USER = env.str("DJANGO_EMAIL_HOST_USER", default="user@yourdomain.com")
EMAIL_HOST_PASSWORD = env.str("DJANGO_EMAIL_HOST_PASSWORD", default="Y0urP@$$w0rd")
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)

# WhiteNoise
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
