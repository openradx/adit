from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from ..models import DicomTask


def reset_tasks(tasks: models.QuerySet["DicomTask"]) -> None:
    tasks.update(
        status=tasks.model.Status.PENDING,
        retries=0,
        message="",
        log="",
        started_at=None,
        ended_at=None,
    )
