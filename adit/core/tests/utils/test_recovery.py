from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connection
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob, ProcrastinateWorker

from adit.core.models import DicomJob, DicomTask
from adit.core.utils import recovery
from adit.mass_transfer.factories import MassTransferJobFactory, MassTransferTaskFactory

from ..example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory
from ..example_app.models import ExampleTransferTask


@pytest.fixture(autouse=True)
def writable_procrastinate(settings):
    # Procrastinate's Django models are read-only by default; the tests create rows.
    settings.PROCRASTINATE_READONLY_MODELS = False


def create_worker(heartbeat_age_seconds: int) -> ProcrastinateWorker:
    return ProcrastinateWorker.objects.create(
        last_heartbeat=timezone.now() - timedelta(seconds=heartbeat_age_seconds)
    )


def create_row(status: str, worker: ProcrastinateWorker | None = None) -> ProcrastinateJob:
    return ProcrastinateJob.objects.create(
        queue_name="dicom",
        task_name="adit.core.tasks.process_dicom_task",
        priority=0,
        args={},
        status=status,
        attempts=0,
        abort_requested=False,
        worker=worker,
    )


def make_stale_task(job_status: str, row: ProcrastinateJob | None) -> ExampleTransferTask:
    job = ExampleTransferJobFactory.create(status=job_status)
    return ExampleTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=row
    )


def owner_gone_q():
    return recovery._owner_gone_q(timezone.now() - timedelta(seconds=30))


def stale_candidates():
    return ExampleTransferTask.objects.filter(status=DicomTask.Status.IN_PROGRESS).filter(
        owner_gone_q()
    )


@pytest.mark.django_db
def test_task_models_include_every_concrete_dicom_task():
    models = recovery.dicom_task_models()
    assert ExampleTransferTask in models
    assert all(issubclass(m, DicomTask) and not m._meta.abstract for m in models)


@pytest.mark.django_db
def test_predicate_matches_task_without_row():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
@pytest.mark.parametrize("row_status", ["todo", "succeeded", "failed", "cancelled", "aborted"])
def test_predicate_matches_row_nobody_is_running(row_status):
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=create_row(row_status))
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
def test_predicate_matches_doing_row_without_worker():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=create_row("doing", worker=None))
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
def test_predicate_matches_doing_row_with_stale_heartbeat():
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
def test_predicate_ignores_doing_row_with_fresh_heartbeat():
    # A task may legitimately run for hours in its subprocess; the parent worker keeps
    # sending heartbeats, so it is not stale.
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=0))
    make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    assert not stale_candidates().exists()


@pytest.mark.django_db
def test_predicate_ignores_aborting_row_with_fresh_heartbeat():
    row = create_row("aborting", worker=create_worker(heartbeat_age_seconds=0))
    make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    assert not stale_candidates().exists()


@pytest.mark.django_db
def test_resolve_orphan_under_live_job_resets_and_requeues():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    task.attempts = 2
    task.save()

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.message == recovery.STALE_TASK_MESSAGE
    assert task.end is None
    assert task.attempts == 2  # the sweep never touches the attempt counter
    assert task.queued_job is not None
    assert task.queued_job.status == "todo"
    assert task.queued_job.task_name == "adit.core.tasks.process_dicom_task"
    assert task.queued_job.queue_name == "dicom"


@pytest.mark.django_db
def test_resolve_mass_transfer_task_requeues_on_its_own_queue():
    job = MassTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    task = MassTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.queued_job is not None
    assert task.queued_job.task_name == "adit.mass_transfer.tasks.process_mass_transfer_task"
    assert task.queued_job.queue_name == "mass_transfer"


@pytest.mark.django_db
@pytest.mark.parametrize("job_status", [DicomJob.Status.CANCELING, DicomJob.Status.CANCELED])
def test_resolve_under_canceling_job_cancels_without_requeue(job_status):
    task = make_stale_task(job_status, row=None)

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "canceled"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.CANCELED
    assert task.message == recovery.STALE_TASK_MESSAGE
    assert task.end is not None
    assert task.queued_job is None
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("row_status", ["todo", "doing"])
def test_resolve_keeps_live_row_and_does_not_requeue(row_status):
    # retry_stalled_jobs will re-deliver this very row; a second row would run the task twice.
    row = create_row(row_status, worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job is None  # link cleared; the row itself is untouched
    assert ProcrastinateJob.objects.count() == 1
    assert ProcrastinateJob.objects.get(pk=row.pk).status == row_status


@pytest.mark.django_db
def test_resolve_declines_when_a_live_worker_owns_the_row():
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=0))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    assert recovery._resolve_stale_task(task, owner_gone_q()) is None

    task.refresh_from_db()
    assert task.status == DicomTask.Status.IN_PROGRESS
    assert task.queued_job_id == row.pk


@pytest.mark.django_db
def test_resolve_declines_when_task_already_finished():
    # The candidate was selected while IN_PROGRESS; the worker finished it in the meantime.
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    ExampleTransferTask.objects.filter(pk=task.pk).update(status=DicomTask.Status.SUCCESS)

    assert recovery._resolve_stale_task(task, owner_gone_q()) is None

    task.refresh_from_db()
    assert task.status == DicomTask.Status.SUCCESS
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.django_db
def test_resolve_twice_changes_nothing_the_second_time():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    stale_copy = ExampleTransferTask.objects.get(pk=task.pk)  # a second sweep's candidate

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"
    assert recovery._resolve_stale_task(stale_copy, owner_gone_q()) is None

    assert ProcrastinateJob.objects.count() == 1


@pytest.mark.django_db
def test_requeue_decision_uses_fresh_read_not_snapshot():
    # The row is deleted between selecting the task and resolving it. The resolve step must
    # notice and re-queue, else the task stays PENDING with no row forever.
    row = create_row("todo", worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    task = ExampleTransferTask.objects.select_related("queued_job").get(pk=task.pk)

    with connection.cursor() as cursor:  # raw delete, like Procrastinate's --delete-jobs
        cursor.execute("DELETE FROM procrastinate_jobs WHERE id = %s", [row.pk])

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.queued_job is not None
    assert task.queued_job.pk != row.pk


@pytest.mark.django_db(transaction=True)
def test_reset_rolls_back_when_requeue_fails():
    # If queuing fails after the reset, the task must stay IN_PROGRESS so the next sweep
    # retries it. A PENDING task without a queue row would never run again.
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)

    with patch.object(
        ExampleTransferTask, "queue_pending_task", autospec=True, side_effect=RuntimeError("db")
    ):
        with pytest.raises(RuntimeError):
            recovery._resolve_stale_task(task, owner_gone_q())

    task.refresh_from_db()
    assert task.status == DicomTask.Status.IN_PROGRESS
