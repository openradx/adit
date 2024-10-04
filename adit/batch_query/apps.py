from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.utils.model_utils import get_model_label

SECTION_NAME = "Batch Query"


class BatchQueryConfig(AppConfig):
    name = "adit.batch_query"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import BatchQueryJob, BatchQueryTask
    from .processors import BatchQueryTaskProcessor

    register_main_menu_item(
        MainMenuItem(
            url_name="batch_query_job_create",
            label=SECTION_NAME,
        )
    )

    register_dicom_processor(get_model_label(BatchQueryTask), BatchQueryTaskProcessor)

    def collect_job_stats():
        counts: dict[BatchQueryJob.Status, int] = {}
        for status in BatchQueryJob.Status:
            counts[status] = BatchQueryJob.objects.filter(status=status).count()
        return JobStats("Batch Query", "batch_query_job_list", counts)

    register_job_stats_collector(collect_job_stats)


def init_db(**kwargs):
    from .models import BatchQuerySettings

    if not BatchQuerySettings.objects.exists():
        BatchQuerySettings.objects.create()
