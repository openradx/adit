from adit_radis_shared.common.management.base.celery_worker import CeleryWorkerCommand


class Command(CeleryWorkerCommand):
    project = "adit"
