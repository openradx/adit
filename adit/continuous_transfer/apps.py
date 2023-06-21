from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.site import register_job_stats_collector, register_main_menu_item


class ContinuousTransferConfig(AppConfig):
    name = "adit.continuous_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="continuous_transfer_job_create",
        label="Continuous Transfer",
    )

    register_job_stats_collector(collect_job_stats)


def collect_job_stats():
    from .models import ContinuousTransferJob

    counts = {}
    for status in ContinuousTransferJob.Status:
        counts[status] = ContinuousTransferJob.objects.filter(status=status).count()

    return {
        "job_name": "Continuous Transfer",
        "url_name": "continuous_transfer_job_list",
        "counts": counts,
    }


def init_db(**kwargs):
    create_group()
    create_app_settings()


def create_group():
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "continuous_transfer_group",
        (
            "continuous_transfer.add_continuoustransferjob",
            "continuous_transfer.view_continuoustransferjob",
        ),
    )


def create_app_settings():
    from .models import ContinuousTransferSettings

    settings = ContinuousTransferSettings.get()
    if not settings:
        ContinuousTransferSettings.objects.create()
