from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.site import (
    register_dicom_processor,
    register_job_stats_collector,
    register_main_menu_item,
)

SECTION_NAME = "Batch Query"


class BatchQueryConfig(AppConfig):
    name = "adit.batch_query"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from .models import BatchQueryTask
    from .processors import BatchQueryTaskProcessor

    register_main_menu_item(
        url_name="batch_query_job_create",
        label=SECTION_NAME,
    )

    model_label = f"{BatchQueryTask._meta.app_label}.{BatchQueryTask._meta.model_name}"
    register_dicom_processor(model_label, BatchQueryTaskProcessor)

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
    create_app_settings()


def create_app_settings():
    from .models import BatchQuerySettings

    settings = BatchQuerySettings.get()
    if not settings:
        BatchQuerySettings.objects.create()
