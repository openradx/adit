from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.site import register_main_menu_item

SECTION_NAME = "DICOM Upload"


class UploadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.upload"

    def ready(self):
        register_app()
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="upload_job_create",
        label=SECTION_NAME,
    )


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import UploadSettings

    settings = UploadSettings.get()
    if not settings:
        UploadSettings.objects.create()
