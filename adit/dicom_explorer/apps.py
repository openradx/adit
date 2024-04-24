from django.apps import AppConfig

SECTION_NAME = "DICOM Explorer"


class DicomExplorerConfig(AppConfig):
    name = "adit.dicom_explorer"

    def ready(self):
        register_app()


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    register_main_menu_item(
        MainMenuItem(
            url_name="dicom_explorer_form",
            label=SECTION_NAME,
        )
    )
