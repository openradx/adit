from unittest.mock import patch

import pytest
from django.core.management import call_command

from adit.core.models import DicomJob, DicomTask

from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory


@pytest.mark.django_db
def test_sweep_command_repairs_stale_task():
    job = ExampleTransferJobFactory.create(status=DicomJob.Status.CANCELING)
    task = ExampleTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    call_command("sweep_stale_tasks")

    task.refresh_from_db()
    assert task.status == DicomTask.Status.CANCELED


@pytest.mark.django_db
def test_sweep_command_exits_zero_when_sweep_raises(capsys):
    # The command runs before bg_worker via &&; a failing sweep must not stop the worker.
    with patch(
        "adit.core.management.commands.sweep_stale_tasks.sweep_stale_dicom_tasks",
        side_effect=RuntimeError("boom"),
    ):
        call_command("sweep_stale_tasks")  # must not raise

    assert "failed" in capsys.readouterr().out
