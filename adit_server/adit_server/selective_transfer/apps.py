from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit_server.core.utils.model_utils import get_model_label

SECTION_NAME = "Selective Transfer"


class SelectiveTransferConfig(AppConfig):
    name = "adit_server.selective_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit_server.core.site import (
        JobStats,
        register_dicom_processor,
        register_job_stats_collector,
    )

    from .models import SelectiveTransferJob, SelectiveTransferTask
    from .processors import SelectiveTransferTaskProcessor

    register_main_menu_item(
        MainMenuItem(
            url_name="selective_transfer_job_create",
            label=SECTION_NAME,
        )
    )

    register_dicom_processor(get_model_label(SelectiveTransferTask), SelectiveTransferTaskProcessor)

    def collect_job_stats() -> JobStats:
        counts: dict[SelectiveTransferJob.Status, int] = {}
        for status in SelectiveTransferJob.Status:
            counts[status] = SelectiveTransferJob.objects.filter(status=status).count()
        return JobStats("Selective Transfer", "selective_transfer_job_list", counts)

    register_job_stats_collector(collect_job_stats)


def init_db(**kwargs):
    from .models import SelectiveTransferSettings

    if not SelectiveTransferSettings.objects.exists():
        SelectiveTransferSettings.objects.create()
