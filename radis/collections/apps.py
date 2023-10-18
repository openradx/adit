from django.apps import AppConfig
from django.db.models.signals import post_migrate

from radis.core.site import register_main_menu_item


class CollectionsConfig(AppConfig):
    name = "radis.collections"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="collection_list",
        label="Collections",
    )


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import CollectionsAppSettings

    settings = CollectionsAppSettings.get()
    if not settings:
        CollectionsAppSettings.objects.create()
