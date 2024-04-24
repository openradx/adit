from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "adit.core"

    def ready(self):
        register_app()


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    register_main_menu_item(
        MainMenuItem(
            url_name="admin_section",
            label="Admin Section",
            staff_only=True,
            order=10,
        )
    )
