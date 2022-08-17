from django.apps import AppConfig


class QidoRsConfig(AppConfig):
    name = 'adit.rest_api.qido_rs'


def init_db(**kwargs):  # pylint: disable=unused-argument
    create_app_settings()


def create_app_settings():
    # pylint: disable=import-outside-toplevel
    from .models import DicomQidoSettings

    settings = DicomQidoSettings.get()
    if not settings:
        DicomQidoSettings.objects.create()