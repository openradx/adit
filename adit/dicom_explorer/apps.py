from django.apps import AppConfig

from adit_radis_shared.common.site import register_main_menu_item

SECTION_NAME = "DICOM Explorer"


class DicomExplorerConfig(AppConfig):
    name = "adit.dicom_explorer"

    def ready(self):
        register_app()


def register_app():
    register_main_menu_item(
        url_name="dicom_explorer_form",
        label=SECTION_NAME,
    )
