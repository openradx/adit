import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import call

import pytest
from django.db import connection
from procrastinate import JobContext
from procrastinate.contrib.django import app
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_mock import MockerFixture

from adit.core.models import DicomJob, DicomTask
from adit.mass_transfer.factories import MassTransferJobFactory, MassTransferTaskFactory
from adit.mass_transfer.tasks import queue_mass_transfer_tasks
from cli import scale_mass_transfer_worker

ROOT_DIR = Path(__file__).resolve().parents[3]
GRACEFUL_TASK_NAME = (
    "adit.mass_transfer.tests.test_scale_mass_transfer_worker.graceful_mass_transfer_test_task"
)


@app.task(queue="mass_transfer", pass_context=True, name=GRACEFUL_TASK_NAME)
def graceful_mass_transfer_test_task(
    context: JobContext,
    sleep_seconds: int = 60,
    poll_interval: float = 0.1,
):
    """Test-only helper that always completes unless forcefully interrupted."""
    deadline = time.monotonic() + sleep_seconds
    while time.monotonic() < deadline:
        _ = context
        time.sleep(poll_interval)


def _build_database_url_from_connection() -> str:
    db_settings = connection.settings_dict
    user = db_settings.get("USER") or ""
    password = db_settings.get("PASSWORD") or ""
    host = db_settings.get("HOST") or "localhost"
    port = db_settings.get("PORT") or "5432"
    name = db_settings["NAME"]
    return f"postgres://{user}:{password}@{host}:{port}/{name}"


def _get_job_status(job_id: int) -> str | None:
    job = ProcrastinateJob.objects.filter(id=job_id).first()
    if not job:
        return None
    return str(job.status)


def _wait_for_status(job_id: int, statuses: set[str], timeout_seconds: int) -> str | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _get_job_status(job_id)
        if status in statuses:
            return status
        time.sleep(0.2)
    return _get_job_status(job_id)


@pytest.mark.django_db(transaction=True)
def test_scale_mass_transfer_worker_scales_up_and_down_without_touching_queued_jobs(
    mocker: MockerFixture,
):
    """Scaling workers must not abort or detach already queued transfer tasks."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task1 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    task2 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    queue_mass_transfer_tasks(job_id=job.pk)

    task1.refresh_from_db()
    task2.refresh_from_db()
    queued_job_ids = {task1.queued_job_id, task2.queued_job_id}
    assert None not in queued_job_ids

    queued_job_ids_int = {job_id for job_id in queued_job_ids if job_id is not None}
    assert (
        set(ProcrastinateJob.objects.filter(id__in=queued_job_ids_int).values_list("id", flat=True))
        == queued_job_ids_int
    )

    helper = mocker.Mock()
    helper.is_production.return_value = True
    helper.get_stack_name.return_value = "adit-prod"
    mocker.patch("cli.cli_helper.CommandHelper", return_value=helper)

    scale_mass_transfer_worker(replicas=3)
    scale_mass_transfer_worker(replicas=0)

    assert helper.execute_cmd.call_args_list == [
        call("docker service scale adit-prod_mass_transfer_worker=3"),
        call("docker service scale adit-prod_mass_transfer_worker=0"),
    ]

    task1.refresh_from_db()
    task2.refresh_from_db()
    assert {task1.queued_job_id, task2.queued_job_id} == queued_job_ids
    assert (
        set(ProcrastinateJob.objects.filter(id__in=queued_job_ids_int).values_list("id", flat=True))
        == queued_job_ids_int
    )


@pytest.mark.django_db(transaction=True)
def test_scale_mass_transfer_worker_scale_down_finishes_current_job_and_blocks_next(
    mocker: MockerFixture,
):
    """Scale-down should let the current task finish and leave queued transfer tasks untouched."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task1 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    task2 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    queue_mass_transfer_tasks(job_id=job.pk)

    task1.refresh_from_db()
    task2.refresh_from_db()

    # Run a deterministic long-running task so we can assert graceful shutdown behavior.
    running_task_seconds = 30
    graceful_timeout_seconds = 50

    running_job_id = app.configure_task(
        GRACEFUL_TASK_NAME,
        allow_unknown=False,
        priority=10_000,
    ).defer(sleep_seconds=running_task_seconds, poll_interval=0.05)

    assert task1.queued_job_id is not None
    assert task2.queued_job_id is not None

    worker_env = os.environ.copy()
    worker_env["DATABASE_URL"] = _build_database_url_from_connection()
    worker_cmd = (
        "import os; "
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adit.settings.development'); "
        "import django; django.setup(); "
        "import adit.mass_transfer.tests.test_scale_mass_transfer_worker; "
        "from django.core.management import execute_from_command_line; "
        "execute_from_command_line(["
        "'manage.py', 'procrastinate', 'worker', '--queues', 'mass_transfer', "
        f"'--shutdown-graceful-timeout', '{graceful_timeout_seconds}', '--delete-jobs', 'never'"
        "])"
    )
    worker_process = subprocess.Popen(
        [sys.executable, "-c", worker_cmd],
        cwd=ROOT_DIR,
        env=worker_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        first_status = _wait_for_status(running_job_id, {"doing"}, timeout_seconds=20)
        assert first_status == "doing"

        helper = mocker.Mock()
        helper.is_production.return_value = True
        helper.get_stack_name.return_value = "adit-prod"
        mocker.patch("cli.cli_helper.CommandHelper", return_value=helper)

        def execute_cmd_side_effect(command: str):
            if command == "docker service scale adit-prod_mass_transfer_worker=0":
                worker_process.send_signal(signal.SIGTERM)

        helper.execute_cmd.side_effect = execute_cmd_side_effect

        scale_mass_transfer_worker(replicas=1)
        scale_mass_transfer_worker(replicas=0)

        worker_process.wait(timeout=running_task_seconds + 20)

        final_running_status = _wait_for_status(
            running_job_id,
            {"succeeded", "failed", "cancelled", "aborted"},
            timeout_seconds=30,
        )
        final_blocked_status_1 = _get_job_status(task1.queued_job_id)
        final_blocked_status_2 = _get_job_status(task2.queued_job_id)

        assert final_running_status == "succeeded"
        assert final_blocked_status_1 == "todo"
        assert final_blocked_status_2 == "todo"
        assert helper.execute_cmd.call_args_list == [
            call("docker service scale adit-prod_mass_transfer_worker=1"),
            call("docker service scale adit-prod_mass_transfer_worker=0"),
        ]
    finally:
        if worker_process.poll() is None:
            worker_process.terminate()
            worker_process.wait(timeout=10)
