from django.apps import AppConfig
from django.db.models.signals import post_migrate

SECTION_NAME = "Selective Transfer"


class SelectiveTransferConfig(AppConfig):
    name = "adit.selective_transfer"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import SelectiveTransferJob, SelectiveTransferTask
    from .processors import SelectiveTransferTaskProcessor

    register_main_menu_item(
        MainMenuItem(
            url_name="selective_transfer_job_create",
            label=SECTION_NAME,
        )
    )

    model_label = (
        f"{SelectiveTransferTask._meta.app_label}.{SelectiveTransferTask._meta.model_name}"
    )
    register_dicom_processor(model_label, SelectiveTransferTaskProcessor)

    def collect_job_stats() -> JobStats:
        counts: dict[SelectiveTransferJob.Status, int] = {}
        for status in SelectiveTransferJob.Status:
            counts[status] = SelectiveTransferJob.objects.filter(status=status).count()
        return JobStats("Selective Transfer", "selective_transfer_job_list", counts)

    register_job_stats_collector(collect_job_stats)


def init_db(**kwargs):
    create_app_settings()


def create_app_settings():
    from .models import SelectiveTransferSettings

    settings = SelectiveTransferSettings.get()
    if not settings:
        SelectiveTransferSettings.objects.create()
