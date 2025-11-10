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


def collect_top_sessions():
    from adit.upload.models import UploadSession

    return list(UploadSession.objects.order_by("-time_opened"))[:5]


def create_app_settings():
    from .models import UploadSettings

    if not UploadSettings.objects.exists():
        UploadSettings.objects.create()
