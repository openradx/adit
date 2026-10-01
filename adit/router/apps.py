from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RouterConfig(AppConfig):
    name = "adit.router"

    def ready(self):
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def init_db(**kwargs):
    from .models import RouterSettings

    if not RouterSettings.objects.exists():
        RouterSettings.objects.create()
