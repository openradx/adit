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
    from adit.core.site import register_dicom_processor

    from .models import RouterTask
    from .processors import RouterTaskProcessor

    register_dicom_processor(get_model_label(RouterTask), RouterTaskProcessor)


def init_db(**kwargs):
    from .models import RouterSettings

    if not RouterSettings.objects.exists():
        RouterSettings.objects.create()
