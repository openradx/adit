from .base import *
from .base import env

# Production settings, see
# https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

DEBUG = False

SECRET_KEY = env('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')

# TODO provide SMTP details, see https://docs.djangoproject.com/en/dev/topics/email/
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
