from adit_radis_shared.common.management.base.celery_beat import CeleryBeatCommand
from django.conf import settings


class Command(CeleryBeatCommand):
    project = "adit"
    paths_to_watch = [settings.BASE_DIR / "adit"]
