from django.apps import AppConfig
from django.db.models.signals import post_migrate
from adit.main.site import register_main_menu_item, register_transfer_job


class ContinuousTransferConfig(AppConfig):
    name = "adit.continuous_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="continuous_transfer_job_create", label="Continuous Transfer"
    )

    # pylint: disable=import-outside-toplevel
    from .models import ContinuousTransferJob
    from .views import ContinuousTransferJobDetailView

    register_transfer_job(
        type_key=ContinuousTransferJob.JOB_TYPE,
        type_name="Continuous Transfer",
        detail_view=ContinuousTransferJobDetailView,
    )


def init_db(**kwargs):  # pylint: disable=unused-argument
    create_group()
    create_app_settings()


def create_group():
    # pylint: disable=import-outside-toplevel
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "continuous_transferrers",
        (
            "continuous_transfer.add_continuoustransferjob",
            "continuous_transfer.view_continuoustransferjob",
        ),
    )


def create_app_settings():
    # pylint: disable=import-outside-toplevel
    from .models import AppSettings

    app_settings = AppSettings.objects.first()
    if not app_settings:
        AppSettings.objects.create()
