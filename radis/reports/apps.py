from django.apps import AppConfig
from django.db.models.signals import post_migrate

from radis.core.site import register_main_menu_item


class ReportsConfig(AppConfig):
    name = "radis.reports"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="search_reports",
        label="Search",
    )


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import ReportsSettings

    settings = ReportsSettings.get()
    if not settings:
        ReportsSettings.objects.create()
