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
def test_cleanup_removes_intermediate_exports_when_converting(tmp_path: Path):
    """When convert_to_nifti=True, EXPORTED volumes hold intermediate DICOM files
    that should be cleaned up on failure.

    Proves: cleanup_on_failure deletes intermediate DICOM exports and marks
    the volume as ERROR when convert_to_nifti is enabled (EXPORTED is not final).
    """
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
        convert_to_nifti=True,
    )
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
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


@pytest.mark.django_db
def test_cleanup_preserves_exported_volumes_when_not_converting(tmp_path: Path):
    """When convert_to_nifti=False, EXPORTED is the final state and the files
    live in the destination folder — cleanup should not delete them.

    Proves: cleanup_on_failure preserves destination files and keeps the EXPORTED
    status when convert_to_nifti is disabled (EXPORTED is the terminal state).
    """
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
        convert_to_nifti=False,
    )
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    export_dir = tmp_path / "output" / "202401" / "PATIENT" / "1-Head"
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
    assert export_dir.exists(), "Exported destination files should be preserved"
    assert volume.status == MassTransferVolume.Status.EXPORTED
    assert volume.exported_folder == str(export_dir)


@pytest.mark.django_db
def test_cleanup_skips_converted_volumes(tmp_path: Path):
    """CONVERTED volumes represent fully-processed data in the destination.

    Proves: cleanup_on_failure never touches CONVERTED volumes — their status
    stays CONVERTED and their destination files are preserved.
    """
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
        convert_to_nifti=True,
    )
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    # Simulate a CONVERTED volume whose intermediate export folder still exists
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
        status=MassTransferVolume.Status.CONVERTED,
        converted_file=str(tmp_path / "output" / "result.nii.gz"),
    )

    task.cleanup_on_failure()

    volume.refresh_from_db()
    # CONVERTED volumes must be left untouched
    assert volume.status == MassTransferVolume.Status.CONVERTED
    assert volume.exported_folder == str(export_dir)
    assert export_dir.exists(), "CONVERTED volume's export folder should not be deleted"


@pytest.mark.django_db
def test_cleanup_deletes_pending_volumes_with_partial_export(tmp_path: Path):
    """PENDING volumes with an exported_folder represent a mid-export crash.

    Proves: cleanup_on_failure removes the partially-written export folder
    and marks the volume as ERROR so it can be re-exported on retry.
    """
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
        convert_to_nifti=True,
    )
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    # A PENDING volume that had its export folder created but fetch_series
    # crashed before setting status to EXPORTED
    partial_dir = tmp_path / "exports" / "202401" / "PATIENT" / "2-Body"
    partial_dir.mkdir(parents=True, exist_ok=True)
    # Write a partial file to simulate incomplete download
    (partial_dir / "partial.dcm").write_bytes(b"incomplete")

    volume = MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        patient_id="PATIENT",
        study_instance_uid="study-1",
        series_instance_uid="series-2",
        modality="CT",
        study_description="",
        series_description="Body",
        series_number=2,
        study_datetime=timezone.now(),
        exported_folder=str(partial_dir),
        status=MassTransferVolume.Status.PENDING,
    )

    task.cleanup_on_failure()

    volume.refresh_from_db()
    assert not partial_dir.exists(), "Partial export should be deleted"
    assert volume.status == MassTransferVolume.Status.ERROR
    assert volume.exported_folder == ""
