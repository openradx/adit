from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.utils.model_utils import get_model_label

SECTION_NAME = "Batch Transfer"


class BatchTransferConfig(AppConfig):
    name = "adit.batch_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import BatchTransferJob, BatchTransferTask
    from .processors import BatchTransferTaskProcessor

    register_main_menu_item(
        MainMenuItem(
            url_name="batch_transfer_job_create",
            label=SECTION_NAME,
        )
    )

    register_dicom_processor(get_model_label(BatchTransferTask), BatchTransferTaskProcessor)

    def collect_job_stats():
        counts: dict[BatchTransferJob.Status, int] = {}
        for status in BatchTransferJob.Status:
            counts[status] = BatchTransferJob.objects.filter(status=status).count()
        return JobStats("Batch Transfer", "batch_transfer_job_list", counts)

    register_job_stats_collector(collect_job_stats)


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import BatchTransferSettings

    if not BatchTransferSettings.objects.exists():
        BatchTransferSettings.objects.create()
