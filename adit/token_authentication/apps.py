from django.apps import AppConfig
from django.db.models.signals import post_migrate
from adit.core.site import register_main_menu_item


class RestAuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.token_authentication"

    def ready(self):
        register_app()

        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(url_name="token_authentication", label="Token Authentication")


def init_db(**kwargs):
    create_group()


def create_group():
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "token_authentication_group", ("token_authentication.manage_auth_tokens",)
    )
