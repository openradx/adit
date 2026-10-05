from typing import Any

from django.utils import timezone

from ..factories import RouterBatchFactory, RouterJobFactory, RouterTaskFactory
from ..models import RouterTask


def create_delivery(status: str, *, files_deleted: bool = False, **job_kwargs: Any) -> RouterTask:
    """Create a router job and its one task, both with *status*.

    The images of their batch are in the spool unless *files_deleted* is set.
    """
    batch = RouterBatchFactory.create(files_deleted_at=timezone.now() if files_deleted else None)
    job = RouterJobFactory.create(status=status, batch=batch, **job_kwargs)
    return RouterTaskFactory.create(job=job, status=status)
