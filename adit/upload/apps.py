from django.apps import AppConfig

from adit.core.site import register_main_menu_item

SECTION_NAME = "Data Upload"


class UploadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.upload"

    def ready(self):
        register_app()


def register_app():
    register_main_menu_item(
        url_name="upload_job_create",
        label=SECTION_NAME,
    )


def init_db(**kwargs):
    create_group()
    create_app_settings()


def create_group():
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "upload_group",
        (
            "upload.add_uploadjob",
            "upload.view_uploadjob",
        ),
    )


def create_app_settings():
    from .models import UploadSettings

    settings = UploadSettings.get()
    if not settings:
        UploadSettings.objects.create()
