from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from ..models import DicomTask

# One advisory lock for every job re-evaluation (task finalizer and sweep alike), so two
# writers never interleave their reads of the task statuses and their job save.
DICOM_JOB_POST_PROCESS_LOCK = "process_dicom_task_lock"


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
