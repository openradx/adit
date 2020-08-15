from django.apps import AppConfig
from django.db.models.signals import post_migrate
from main.site import register_main_menu_item, register_transfer_job


class SelectiveTransferConfig(AppConfig):
    name = "selective_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(url_name="query_studies", label="Selective Transfer")

    # pylint: disable=import-outside-toplevel
    from .models import SelectiveTransferJob
    from .views import SelectiveTransferJobDetail

    register_transfer_job(
        type_key=SelectiveTransferJob.JOB_TYPE,
        type_name="Selective transfer job",
        detail_view=SelectiveTransferJobDetail,
    )


def init_db(**kwargs):  # pylint: disable=unused-argument
    create_group()
    create_app_settings()


def create_group():
    # pylint: disable=import-outside-toplevel
    from accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "selective_transferrers",
        (
            "selective_transfer.add_selectivetransferjob",
            "selective_transfer.view_selectivetransferjob",
        ),
    )


def create_app_settings():
    # pylint: disable=import-outside-toplevel
    from .models import AppSettings

    app_settings = AppSettings.objects.first()
    if not app_settings:
        AppSettings.objects.create()
