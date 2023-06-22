from datetime import time

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class WadorsConfig(AppConfig):
    name = "adit.dicom_web.wadors"

    def ready(self):
        post_migrate.connect(init_db, sender=self)


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import DicomWadoSettings

    settings = DicomWadoSettings.get()
    if not settings:
        DicomWadoSettings.objects.create(slot_begin_time=time(8, 8), slot_end_time=time(8, 8))
