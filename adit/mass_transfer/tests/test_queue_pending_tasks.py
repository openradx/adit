import pytest
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
    """After queue_mass_transfer_tasks runs, all pending tasks should have
    queued_job set and be placed on the mass_transfer queue."""
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
def test_background_job_skips_canceled_tasks():
    """Canceled tasks should not be queued."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    pending_task = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    canceled_task = MassTransferTaskFactory.create(status=DicomTask.Status.CANCELED, job=job)

    queue_mass_transfer_tasks(job_id=job.pk)

    pending_task.refresh_from_db()
    canceled_task.refresh_from_db()
    assert pending_task.queued_job is not None
    assert canceled_task.queued_job is None


@pytest.mark.django_db(transaction=True)
def test_background_job_is_idempotent():
    """Calling queue_mass_transfer_tasks twice should not double-queue tasks."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task1 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)
    task2 = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    queue_mass_transfer_tasks(job_id=job.pk)

    task1.refresh_from_db()
    task2.refresh_from_db()
    first_queued_job_1 = task1.queued_job_id
    first_queued_job_2 = task2.queued_job_id
    assert first_queued_job_1 is not None
    assert first_queued_job_2 is not None

    # Call again — tasks already have queued_job set, so they should be skipped
    queue_mass_transfer_tasks(job_id=job.pk)

    task1.refresh_from_db()
    task2.refresh_from_db()
    assert task1.queued_job_id == first_queued_job_1
    assert task2.queued_job_id == first_queued_job_2


@pytest.mark.django_db(transaction=True)
def test_background_job_skips_deleted_job():
    """If the job is deleted before the background task runs, it should
    gracefully skip."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    job_id = job.pk
    job.delete()

    # Should not raise
    queue_mass_transfer_tasks(job_id=job_id)


@pytest.mark.django_db(transaction=True)
def test_background_job_skips_non_pending_job():
    """If the job status changes before the background task runs (e.g. cancel),
    tasks should not be queued."""
    job = MassTransferJobFactory.create(status=DicomJob.Status.PENDING)
    task = MassTransferTaskFactory.create(status=DicomTask.Status.PENDING, job=job)

    # Simulate cancel happening before the background job runs
    job.status = DicomJob.Status.CANCELED
    job.save()

    queue_mass_transfer_tasks(job_id=job.pk)

    task.refresh_from_db()
    assert task.queued_job is None


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
