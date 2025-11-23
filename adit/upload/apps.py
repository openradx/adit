from django.apps import AppConfig

SECTION_NAME = "DICOM Upload"


class UploadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.upload"

    def ready(self):
        register_app()


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    register_main_menu_item(
        MainMenuItem(
            url_name="upload_create",
            label=SECTION_NAME,
        )
    )


def create_app_settings():
    from .models import UploadSettings

    if not UploadSettings.objects.exists():
        UploadSettings.objects.create()
