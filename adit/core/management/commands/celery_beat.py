from adit_radis_shared.common.management.base.celery_beat import CeleryBeatCommand


class Command(CeleryBeatCommand):
    project = "adit"
