from datetime import time

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class DicomWebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.dicom_web"

    def ready(self):
        post_migrate.connect(init_db, sender=self)


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import DicomWebSettings

    settings = DicomWebSettings.get()
    if not settings:
        DicomWebSettings.objects.create(slot_begin_time=time(8, 8), slot_end_time=time(8, 8))
