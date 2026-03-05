import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.utils import timezone

from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.mass_transfer.models import (
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)


@pytest.mark.django_db
def test_cleanup_on_failure_is_noop():
    """With deferred insertion, cleanup_on_failure has nothing to do.

    Volumes are only created in the DB after successful export/conversion,
    and temp directories are cleaned up by TemporaryDirectory context managers.
    """
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    job = MassTransferJob.objects.create(
        owner=user,
        source=source,
        destination=destination,
        start_date=timezone.now().date(),
        end_date=timezone.now().date(),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    # Create some volumes in various states
    MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        patient_id="PATIENT",
        study_instance_uid="study-1",
        series_instance_uid="series-1",
        modality="CT",
        study_description="",
        series_description="Head",
        series_number=1,
        study_datetime=timezone.now(),
        status=MassTransferVolume.Status.EXPORTED,
    )

    # Should not raise or modify anything
    task.cleanup_on_failure()

    vol = MassTransferVolume.objects.get(series_instance_uid="series-1")
    assert vol.status == MassTransferVolume.Status.EXPORTED
