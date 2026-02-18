from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.utils.model_utils import get_model_label

SECTION_NAME = "Mass Transfer"


class MassTransferConfig(AppConfig):
    name = "adit.mass_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import MassTransferJob, MassTransferTask
    from .processors import MassTransferTaskProcessor

    register_main_menu_item(
        MainMenuItem(
            url_name="mass_transfer_job_create",
            label=SECTION_NAME,
        )
    )

    register_dicom_processor(get_model_label(MassTransferTask), MassTransferTaskProcessor)

    def collect_job_stats() -> JobStats:
        counts: dict[MassTransferJob.Status, int] = {}
        for status in MassTransferJob.Status:
            counts[status] = MassTransferJob.objects.filter(status=status).count()
        return JobStats("Mass Transfer", "mass_transfer_job_list", counts)

    register_job_stats_collector(collect_job_stats)


def init_db(**kwargs):
    from .models import MassTransferSettings

    if not MassTransferSettings.objects.exists():
        MassTransferSettings.objects.create()
