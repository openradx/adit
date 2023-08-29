from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TokenAuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adit.token_authentication"

    def ready(self):
        post_migrate.connect(init_db, sender=self)


def init_db(**kwargs):
    create_group()


def create_group():
    from adit.shared.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "token_authentication_group",
        (
            "token_authentication.add_token",
            "token_authentication.delete_token",
            "token_authentication.view_token",
        ),
    )
