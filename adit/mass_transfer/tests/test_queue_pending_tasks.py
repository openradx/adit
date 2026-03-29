import pytest
from adit_radis_shared.common.utils.testing_helpers import run_worker_once
from procrastinate.contrib.django.models import ProcrastinateJob

from adit.core.models import DicomJob, DicomTask

from ..factories import MassTransferJobFactory, MassTransferTaskFactory
from ..tasks import queue_mass_transfer_tasks


@pytest.mark.django_db(transaction=True)
def test_queue_pending_tasks_defers_background_job():
    """queue_pending_tasks() should defer a single job on the default queue
    without queuing individual tasks inline."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    job.queue_pending_tasks()

    # A single queueing job should be deferred on the default queue
    queueing_jobs = ProcrastinateJob.objects.filter(
        task_name="adit.mass_transfer.tasks.queue_mass_transfer_tasks"
    )
    assert queueing_jobs.count() == 1
    queueing_job = queueing_jobs.first()
    assert queueing_job is not None
    assert queueing_job.queue_name == "default"

    # Individual tasks should NOT have been queued yet
    for task in job.tasks.all():
        assert task.queued_job is None


@pytest.mark.django_db(transaction=True)
def test_background_job_queues_all_pending_tasks():
    """After the background job runs, all pending tasks should have been
    picked up by the worker (status progressed beyond PENDING)."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task1 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    task2 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    job.queue_pending_tasks()
    run_worker_once()

    # run_worker_once processes all jobs (queueing + processing) and deletes
    # ProcrastinateJob records. Verify that tasks were actually processed.
    task1.refresh_from_db()
    task2.refresh_from_db()
    assert task1.status != DicomTask.Status.PENDING
    assert task2.status != DicomTask.Status.PENDING


@pytest.mark.django_db(transaction=True)
def test_background_job_skips_canceled_tasks():
    """Canceled tasks should not be queued."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    pending_task = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    canceled_task = MassTransferTaskFactory.create(status=DicomTask.Status.CANCELED, job=job)

    job.queue_pending_tasks()
    run_worker_once()

    pending_task.refresh_from_db()
    canceled_task.refresh_from_db()
    assert pending_task.status != DicomTask.Status.PENDING
    assert canceled_task.status == DicomTask.Status.CANCELED


@pytest.mark.django_db(transaction=True)
def test_background_job_is_idempotent():
    """Deferring queue_pending_tasks twice should not double-queue tasks."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task1 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    task2 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    job.queue_pending_tasks()
    run_worker_once()

    task1.refresh_from_db()
    task2.refresh_from_db()
    assert task1.attempts == 1
    assert task2.attempts == 1

    # Reset job to PENDING and defer again
    job.refresh_from_db()
    job.status = DicomJob.Status.PENDING
    job.save()
    job.queue_pending_tasks()
    run_worker_once()

    # Tasks should not have been processed again (status is no longer PENDING)
    task1.refresh_from_db()
    task2.refresh_from_db()
    assert task1.attempts == 1
    assert task2.attempts == 1


@pytest.mark.django_db(transaction=True)
def test_background_job_skips_deleted_job():
    """If the job is deleted before the background task runs, it should
    gracefully skip."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    job.queue_pending_tasks()
    job.delete()

    # Should not raise
    run_worker_once()


@pytest.mark.django_db(transaction=True)
def test_background_job_skips_non_pending_job():
    """If the job status changes before the background task runs (e.g. cancel),
    tasks should not be queued."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    job.queue_pending_tasks()

    # Simulate cancel happening before the background job runs
    job.status = DicomJob.Status.CANCELED
    job.save()

    run_worker_once()

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING


@pytest.mark.django_db(transaction=True)
def test_queue_mass_transfer_tasks_sets_queued_job():
    """Calling queue_mass_transfer_tasks directly should set queued_job
    on each pending task and place them on the mass_transfer queue."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task1 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    task2 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    queue_mass_transfer_tasks(job_id=job.pk)

    task1.refresh_from_db()
    task2.refresh_from_db()
    assert task1.queued_job is not None
    assert task2.queued_job is not None

    for task in [task1, task2]:
        procrastinate_job = ProcrastinateJob.objects.get(pk=task.queued_job_id)
        assert procrastinate_job.queue_name == "mass_transfer"


@pytest.mark.django_db(transaction=True)
def test_queue_mass_transfer_tasks_uses_urgent_priority():
    """Urgent jobs should queue tasks with urgent priority."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING, urgent=True)
    task = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    queue_mass_transfer_tasks(job_id=job.pk)

    task.refresh_from_db()
    procrastinate_job = ProcrastinateJob.objects.get(pk=task.queued_job_id)
    assert procrastinate_job.priority == job.urgent_priority
