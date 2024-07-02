from django.apps import AppConfig
from django.db.models.signals import post_migrate

SECTION_NAME = "DICOM Upload"


class UploadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.upload"

    def ready(self):
        register_app()
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    register_main_menu_item(
        MainMenuItem(
            url_name="upload_job_create",
            label=SECTION_NAME,
        )
    )



def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import UploadSettings

    if not UploadSettings.objects.exists():
        UploadSettings.objects.create()
