from datetime import timedelta

import pytest
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob, ProcrastinateWorker

from adit.core.models import DicomJob, DicomTask
from adit.core.utils import recovery

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
