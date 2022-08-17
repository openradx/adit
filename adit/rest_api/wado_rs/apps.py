from django.apps import AppConfig


class WadoRsConfig(AppConfig):
    name = 'adit.rest_api.wado_rs'


def init_db(**kwargs):  # pylint: disable=unused-argument
    create_app_settings()


def create_app_settings():
    # pylint: disable=import-outside-toplevel
    from .models import DicomWadoSettings

    settings = DicomWadoSettings.get()
    if not settings:
        DicomWadoSettings.objects.create()

