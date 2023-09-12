from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = "adit.core"

    def ready(self):
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def init_db(sender, **kwargs):
    create_app_settings()


def create_app_settings():
    from .models import CoreSettings

    settings = CoreSettings.get()
    if not settings:
        CoreSettings.objects.create()
