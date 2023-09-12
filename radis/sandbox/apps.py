from django.apps import AppConfig

from radis.core.site import register_main_menu_item

SECTION_NAME = "Sandbox"


class SandboxConfig(AppConfig):
    name = "radis.sandbox"

    def ready(self):
        register_app()


def register_app():
    register_main_menu_item(
        url_name="sandbox_list",
        label=SECTION_NAME,
    )
