from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ExampleAppConfig(AppConfig):
    name = "adit.core.tests.example_app"

    def ready(self):
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def init_db(sender, **kwargs):
    create_app_settings()


def create_app_settings():
    from .models import ExampleAppSettings

    if not ExampleAppSettings.objects.exists():
        ExampleAppSettings.objects.create()
