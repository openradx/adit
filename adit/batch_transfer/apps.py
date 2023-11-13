from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.site import (
    register_dicom_processor,
    register_job_stats_collector,
    register_main_menu_item,
)

SECTION_NAME = "Batch Transfer"


class BatchTransferConfig(AppConfig):
    name = "adit.batch_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from .models import BatchTransferTask
    from .processors import BatchTransferTaskProcessor

    register_main_menu_item(
        url_name="batch_transfer_job_create",
        label=SECTION_NAME,
    )

    model_label = f"{BatchTransferTask._meta.app_label}.{BatchTransferTask._meta.model_name}"
    register_dicom_processor(model_label, BatchTransferTaskProcessor)

    register_job_stats_collector(collect_job_stats)


def collect_job_stats():
    from .models import BatchTransferJob

    counts = {}
    for status in BatchTransferJob.Status:
        counts[status] = BatchTransferJob.objects.filter(status=status).count()

    return {
        "job_name": "Batch Transfer",
        "url_name": "batch_transfer_job_list",
        "counts": counts,
    }


def init_db(**kwargs):
    create_group()
    create_app_settings()


def create_group():
    from adit.accounts.utils import create_group_with_permissions

    create_group_with_permissions(
        "batch_transfer_group",
        (
            "batch_transfer.add_batchtransferjob",
            "batch_transfer.view_batchtransferjob",
        ),
    )


def create_app_settings():
    from .models import BatchTransferSettings

    settings = BatchTransferSettings.get()
    if not settings:
        BatchTransferSettings.objects.create()
