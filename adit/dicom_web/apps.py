from django.apps import AppConfig
from django.db.models.signals import post_migrate


class DicomWebConfig(AppConfig):
    name = "adit.dicom_web"

    def ready(self):
        post_migrate.connect(init_db, sender=self)


def init_db(**kwargs):
    from .models import DicomWebSettings

    if not DicomWebSettings.objects.exists():
        DicomWebSettings.objects.create()


def collect_top_sessions():
    from .models import APISession

    return list(APISession.objects.order_by("-time_opened"))[:5]
