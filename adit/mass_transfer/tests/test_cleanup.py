from pathlib import Path

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
def test_cleanup_mass_transfer_exports_on_failure(tmp_path: Path):
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
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
        task_type=MassTransferTask.TaskType.PROCESSING,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
        study_instance_uid="study-1",
        patient_id="PATIENT",
    )

    export_dir = tmp_path / "exports" / "202401" / "PATIENT" / "1-Head"
    export_dir.mkdir(parents=True, exist_ok=True)

    volume = MassTransferVolume.objects.create(
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
        exported_folder=str(export_dir),
        status=MassTransferVolume.Status.EXPORTED,
    )

    task.cleanup_on_failure()

    volume.refresh_from_db()
    assert not export_dir.exists()
    assert volume.status == MassTransferVolume.Status.ERROR
    assert volume.exported_folder == ""
