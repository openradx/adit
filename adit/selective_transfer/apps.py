from django.apps import AppConfig
from django.db.models.signals import post_migrate
from adit.core.site import register_job_stats_collector, register_main_menu_item


class SelectiveTransferConfig(AppConfig):
    name = "adit.selective_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="selective_transfer_job_create",
        label="Selective Transfer",
    )

    register_job_stats_collector(collect_job_stats)


def collect_job_stats():
    from .models import SelectiveTransferJob

    counts = {}
    for status in SelectiveTransferJob.Status:
        counts[status] = SelectiveTransferJob.objects.filter(status=status).count()

    return {
        "job_name": "Selective Transfer",
        "url_name": "selective_transfer_job_list",
        "counts": counts,
    }


def init_db(**kwargs):
    create_group()
    create_app_settings()


def create_group():
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "selective_transfer_group",
        (
            "selective_transfer.add_selectivetransferjob",
            "selective_transfer.view_selectivetransferjob",
        ),
    )


def create_app_settings():
    from .models import SelectiveTransferSettings

    settings = SelectiveTransferSettings.get()
    if not settings:
        SelectiveTransferSettings.objects.create()
