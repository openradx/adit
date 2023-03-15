from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.site import register_job_stats_collector, register_main_menu_item


class BatchQueryConfig(AppConfig):
    name = "adit.batch_query"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    register_main_menu_item(
        url_name="batch_query_job_create",
        label="Batch Query",
    )

    register_job_stats_collector(collect_job_stats)


def collect_job_stats():
    from .models import BatchQueryJob

    counts = {}
    for status in BatchQueryJob.Status:
        counts[status] = BatchQueryJob.objects.filter(status=status).count()

    return {
        "job_name": "Batch Query",
        "url_name": "batch_query_job_list",
        "counts": counts,
    }


def init_db(**kwargs):
    create_group()
    create_app_settings()


def create_group():
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "batch_query_group",
        (
            "batch_query.add_batchqueryjob",
            "batch_query.view_batchqueryjob",
        ),
    )


def create_app_settings():
    from .models import BatchQuerySettings

    settings = BatchQuerySettings.get()
    if not settings:
        BatchQuerySettings.objects.create()
