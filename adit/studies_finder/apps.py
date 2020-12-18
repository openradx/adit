from django.apps import AppConfig
from django.db.models.signals import post_migrate
from adit.core.site import register_main_menu_item


class StudiesFinderConfig(AppConfig):
    name = "adit.studies_finder"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="studies_finder_job_create",
        label="Studies Finder",
    )


def init_db(**kwargs):  # pylint: disable=unused-argument
    create_group()
    create_app_settings()


def create_group():
    # pylint: disable=import-outside-toplevel
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "studies_finders",
        (
            "studies_finder.add_studiesfinderjob",
            "studies_finder.view_studiesfinderjob",
        ),
    )


def create_app_settings():
    # pylint: disable=import-outside-toplevel
    from .models import StudiesFinderSettings

    settings = StudiesFinderSettings.get()
    if not settings:
        StudiesFinderSettings.objects.create()
