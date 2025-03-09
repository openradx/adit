from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from ..models import DicomTask


def get_model_label(model: type[models.Model]) -> str:
    return f"{model._meta.app_label}.{model._meta.model_name}"


def reset_tasks(tasks: models.QuerySet["DicomTask"]) -> None:
    tasks.update(
        status=tasks.model.Status.PENDING,
        queued_job_id=None,
        attempts=0,
        message="",
        log="",
        start=None,
        end=None,
    )
