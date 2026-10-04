from django.apps import AppConfig
from django.db.models.signals import post_migrate

from adit.core.utils.model_utils import get_model_label


class RouterConfig(AppConfig):
    name = "adit.router"

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def register_app():
    from adit_radis_shared.common.site import MainMenuItem, register_main_menu_item

    from adit.core.site import JobStats, register_dicom_processor, register_job_stats_collector

    from .models import RouterJob, RouterTask
    from .processors import RouterTaskProcessor

    # Staff-only like the Admin Section, and listed right before it.
    register_main_menu_item(
        MainMenuItem(url_name="router_rule_list", label="Router", order=9, staff_only=True)
    )

    register_dicom_processor(get_model_label(RouterTask), RouterTaskProcessor)

    def collect_job_stats() -> JobStats:
        counts: dict[RouterJob.Status, int] = {}
        for status in RouterJob.Status:
            counts[status] = RouterJob.objects.filter(status=status).count()
        return JobStats("Router", "router_job_list", counts)

    register_job_stats_collector(collect_job_stats)


def init_db(**kwargs):
    from .models import RouterSettings

    if not RouterSettings.objects.exists():
        RouterSettings.objects.create()
