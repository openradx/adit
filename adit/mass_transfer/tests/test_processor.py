import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.utils import timezone
from pytest_mock import MockerFixture

from adit.core.errors import DicomError
from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.utils.dicom_operator import DicomOperator
from adit.mass_transfer.models import (
    MassTransferFilter,
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)
from adit.mass_transfer.processors import MassTransferTaskProcessor, _volume_output_path


@pytest.mark.django_db
def test_find_studies_raises_when_time_window_too_small(mocker: MockerFixture, settings):
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 1
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    job = MassTransferJob.objects.create(
        owner=user,
        source=source,
        destination=destination,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )
    mf = MassTransferFilter.objects.create(owner=user, name="CT Filter", modality="CT")
    job.filters.add(mf)

    start = timezone.now()
    end = start + timedelta(minutes=10)
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=start,
        partition_end=end,
        partition_key="20240101",
    )

    processor = MassTransferTaskProcessor(task)
    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.return_value = [object(), object()]

    with pytest.raises(DicomError, match="Time window too small"):
        processor._find_studies(operator, mf, start, end)


@pytest.mark.django_db
def test_process_groups_pseudonyms_by_study(mocker: MockerFixture, settings, tmp_path: Path):
    settings.MASS_TRANSFER_EXPORT_BASE_DIR = str(tmp_path / "exports")
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
    job = MassTransferJob.objects.create(
        owner=user,
        source=source,
        destination=destination,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )
    mf = MassTransferFilter.objects.create(owner=user, name="CT Filter", modality="CT")
    job.filters.add(mf)

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    volume1 = MassTransferVolume.objects.create(
        job=job,
        partition_key="20240101",
        study_instance_uid="study-1",
        series_instance_uid="series-1",
        modality="CT",
        study_description="",
        series_description="A",
        series_number=1,
        study_datetime=timezone.now(),
    )
    volume2 = MassTransferVolume.objects.create(
        job=job,
        partition_key="20240101",
        study_instance_uid="study-1",
        series_instance_uid="series-2",
        modality="CT",
        study_description="",
        series_description="B",
        series_number=2,
        study_datetime=timezone.now(),
    )
    volume3 = MassTransferVolume.objects.create(
        job=job,
        partition_key="20240101",
        study_instance_uid="study-2",
        series_instance_uid="series-3",
        modality="CT",
        study_description="",
        series_description="C",
        series_number=3,
        study_datetime=timezone.now(),
    )

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(
        processor,
        "_find_volumes",
        return_value=[volume1, volume2, volume3],
    )

    export_calls: list[tuple[str, str]] = []

    def fake_export(_, volume, __, pseudonym):
        export_calls.append((volume.series_instance_uid, pseudonym))

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)
    mocker.patch.object(processor, "_convert_volume", return_value=None)

    uuid_side_effect = [
        uuid.UUID(int=1),
        uuid.UUID(int=2),
    ]
    mocker.patch("adit.mass_transfer.processors.uuid.uuid4", side_effect=uuid_side_effect)

    result = processor.process()

    pseudonyms_by_series = {series_uid: pseudonym for series_uid, pseudonym in export_calls}
    assert pseudonyms_by_series["series-1"] == pseudonyms_by_series["series-2"]
    assert pseudonyms_by_series["series-1"] != pseudonyms_by_series["series-3"]
    assert result["status"] == MassTransferTask.Status.SUCCESS


@pytest.mark.django_db
def test_process_opt_out_skips_pseudonymization(
    mocker: MockerFixture,
    settings,
    tmp_path: Path,
):
    settings.MASS_TRANSFER_EXPORT_BASE_DIR = str(tmp_path / "exports")
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
    job = MassTransferJob.objects.create(
        owner=user,
        source=source,
        destination=destination,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        pseudonymize=False,
    )
    mf = MassTransferFilter.objects.create(owner=user, name="CT Filter", modality="CT")
    job.filters.add(mf)

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    volume = MassTransferVolume.objects.create(
        job=job,
        partition_key="20240101",
        patient_id="PATIENT-1",
        study_instance_uid="study-1",
        series_instance_uid="series-1",
        modality="CT",
        study_description="",
        series_description="A",
        series_number=1,
        study_datetime=timezone.now(),
    )

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_find_volumes", return_value=[volume])

    export_calls: list[str] = []

    def fake_export(_, __, ___, pseudonym):
        export_calls.append(pseudonym)

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)
    mocker.patch.object(processor, "_convert_volume", return_value=None)

    result = processor.process()

    assert export_calls == [""]
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_volume_output_path_uses_year_month_and_subject_id():
    base_dir = Path("/tmp/base")
    study_dt = datetime(2024, 2, 15, 10, 30)
    path = _volume_output_path(base_dir, study_dt, "subject", "1-Head")

    assert path == base_dir / "202402" / "subject" / "1-Head"
