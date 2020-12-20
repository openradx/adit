from django.apps import AppConfig
from django.db.models.signals import post_migrate
from adit.core.site import register_main_menu_item


class StudyFinderConfig(AppConfig):
    name = "adit.study_finder"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="study_finder_job_create",
        label="Study Finder",
    )


def init_db(**kwargs):  # pylint: disable=unused-argument
    create_group()
    create_app_settings()


def create_group():
    # pylint: disable=import-outside-toplevel
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "study_finders",
        (
            "study_finder.add_studyfinderjob",
            "study_finder.view_studyfinderjob",
        ),
    )


def create_app_settings():
    # pylint: disable=import-outside-toplevel
    from .models import StudyFinderSettings

    settings = StudyFinderSettings.get()
    if not settings:
        StudyFinderSettings.objects.create()
