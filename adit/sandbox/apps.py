from django.apps import AppConfig

from adit.core.site import register_main_menu_item

SECTION_NAME = "Sandbox"


class SandboxConfig(AppConfig):
    name = "adit.sandbox"

    def ready(self):
        register_app()


def register_app():
    register_main_menu_item(
        url_name="sandbox_list",
        label=SECTION_NAME,
    )
