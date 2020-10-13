from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MainConfig(AppConfig):
    name = "adit.main"

    def ready(self):
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def init_db(sender, **kwargs):  # pylint: disable=unused-argument
    create_app_settings()


def create_app_settings():
    from .models import MainSettings  # pylint: disable=import-outside-toplevel

    settings = MainSettings.get()
    if not settings:
        MainSettings.objects.create()
