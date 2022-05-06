from django.apps import AppConfig
from adit.core.site import register_main_menu_item


class RestAuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.token_authentication"

    def ready(self):
        register_app()


def register_app():
    register_main_menu_item(
        url_name="token_authentication", label="Token Authentication"
    )
