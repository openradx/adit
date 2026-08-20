import logging
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
from ..example_app.models import ExampleTransferJob, ExampleTransferTask


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
def test_resolve_keeps_live_row_and_its_link_and_does_not_requeue(row_status):
    # retry_stalled_jobs will re-deliver this very row; a second row would run the task
    # twice. The task keeps pointing at the row, so after the row runs again the sweep
    # still sees who owns the task.
    row = create_row(row_status, worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job_id == row.pk
    assert ProcrastinateJob.objects.count() == 1
    assert ProcrastinateJob.objects.get(pk=row.pk).status == row_status


@pytest.mark.django_db
def test_second_sweep_tick_leaves_the_recovered_run_alone():
    # The 9a bug shape: crash -> sweep resets the task but leaves the row to run again ->
    # the row runs again on a healthy worker -> the next sweep tick must not touch the
    # running task or create a second row.
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job_id == row.pk

    # retry_stalled_jobs hands the same row to a healthy worker, whose claim takes the
    # task (mirrors the claim UPDATE in adit/core/tasks.py including the owner stamp).
    ProcrastinateJob.objects.filter(pk=row.pk).update(worker=create_worker(heartbeat_age_seconds=0))
    claimed = ExampleTransferTask.objects.filter(
        pk=task.pk, status=DicomTask.Status.PENDING
    ).update(status=DicomTask.Status.IN_PROGRESS, start=timezone.now(), queued_job_id=row.pk)
    assert claimed == 1

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    assert task.status == DicomTask.Status.IN_PROGRESS
    assert task.queued_job_id == row.pk
    assert ProcrastinateJob.objects.count() == 1


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


@pytest.mark.django_db
def test_sweep_drains_job_stuck_in_canceling():
    # Worker killed while a task ran, row gone, user pressed Cancel: nothing ends the job.
    task = make_stale_task(DicomJob.Status.CANCELING, row=None)

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    task.job.refresh_from_db()
    assert task.status == DicomTask.Status.CANCELED
    assert task.job.status == DicomJob.Status.CANCELED
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.django_db
def test_sweep_requeues_orphan_and_job_goes_back_to_pending():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    task.job.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job is not None
    assert task.job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_sweep_leaves_running_and_finished_tasks_alone():
    running = make_stale_task(
        DicomJob.Status.IN_PROGRESS,
        row=create_row("doing", worker=create_worker(heartbeat_age_seconds=0)),
    )
    job = ExampleTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    pending = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.PENDING)
    done = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

    recovery.sweep_stale_dicom_tasks()

    for task, status in (
        (running, DicomTask.Status.IN_PROGRESS),
        (pending, DicomTask.Status.PENDING),
        (done, DicomTask.Status.SUCCESS),
    ):
        task.refresh_from_db()
        assert task.status == status
    assert ProcrastinateJob.objects.count() == 1


@pytest.mark.django_db
def test_sweep_reevaluates_finished_job_with_stray_in_progress_task():
    # Should not happen, but a repaired task must never hang under a finished job.
    job = ExampleTransferJobFactory.create(status=DicomJob.Status.SUCCESS)
    ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
    stray = ExampleTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    recovery.sweep_stale_dicom_tasks()

    stray.refresh_from_db()
    job.refresh_from_db()
    assert stray.status == DicomTask.Status.PENDING
    assert job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_sweep_covers_every_task_model():
    example = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    mass_job = MassTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    mass = MassTransferTaskFactory.create(
        job=mass_job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    recovery.sweep_stale_dicom_tasks()

    example.refresh_from_db()
    mass.refresh_from_db()
    assert example.status == DicomTask.Status.PENDING
    assert mass.status == DicomTask.Status.PENDING


@pytest.mark.django_db
def test_sweep_logs_info_only_when_something_was_repaired(caplog):
    caplog.set_level(logging.DEBUG, logger="adit.core.utils.recovery")

    recovery.sweep_stale_dicom_tasks()
    recovery_info = [
        r
        for r in caplog.records
        if r.levelno == logging.INFO and r.name == "adit.core.utils.recovery"
    ]
    assert not recovery_info

    make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    recovery.sweep_stale_dicom_tasks()
    recovery_info = [
        r
        for r in caplog.records
        if r.levelno == logging.INFO and r.name == "adit.core.utils.recovery"
    ]
    assert len(recovery_info) == 1
    assert "ExampleTransferTask 1 (1 pending, 0 canceled)" in recovery_info[0].getMessage()


@pytest.mark.django_db
def test_sweep_repairs_remaining_tasks_when_one_repair_fails():
    broken = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    mass_job = MassTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    healthy = MassTransferTaskFactory.create(
        job=mass_job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    with patch.object(
        ExampleTransferTask, "queue_pending_task", autospec=True, side_effect=RuntimeError("db")
    ):
        with pytest.raises(RuntimeError, match="1 error"):
            recovery.sweep_stale_dicom_tasks()

    broken.refresh_from_db()
    healthy.refresh_from_db()
    mass_job.refresh_from_db()
    assert broken.status == DicomTask.Status.IN_PROGRESS  # rolled back; next tick retries
    assert healthy.status == DicomTask.Status.PENDING
    assert mass_job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_sweep_reevaluates_remaining_jobs_when_one_recount_fails():
    broken_task = make_stale_task(DicomJob.Status.CANCELING, row=None)
    healthy_task = make_stale_task(DicomJob.Status.CANCELING, row=None)
    real_post_process = ExampleTransferJob.post_process

    def failing_post_process(self, *args, **kwargs):
        if self.pk == broken_task.job.pk:
            raise RuntimeError("mail bounced")
        return real_post_process(self, *args, **kwargs)

    with patch.object(
        ExampleTransferJob, "post_process", autospec=True, side_effect=failing_post_process
    ):
        with pytest.raises(RuntimeError, match="1 error"):
            recovery.sweep_stale_dicom_tasks()

    broken_task.refresh_from_db()
    healthy_task.refresh_from_db()
    broken_task.job.refresh_from_db()
    healthy_task.job.refresh_from_db()
    assert broken_task.status == DicomTask.Status.CANCELED
    assert healthy_task.status == DicomTask.Status.CANCELED
    # The broken job keeps its old status until something re-evaluates it (documented
    # residual: its tasks are repaired, so no later sweep tick revisits it by itself).
    assert broken_task.job.status == DicomJob.Status.CANCELING
    assert healthy_task.job.status == DicomJob.Status.CANCELED
