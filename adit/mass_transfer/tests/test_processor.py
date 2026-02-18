import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.utils import timezone
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.core.errors import DicomError
from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.mass_transfer.models import (
    MassTransferFilter,
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)
from adit.mass_transfer.processors import MassTransferTaskProcessor, _volume_path


def _make_study(study_uid: str, study_date: str = "20240101") -> ResultDataset:
    """Create a minimal ResultDataset for testing _find_studies."""
    ds = Dataset()
    ds.StudyInstanceUID = study_uid
    ds.StudyDate = study_date
    ds.StudyTime = "120000"
    ds.PatientID = "PAT1"
    ds.ModalitiesInStudy = ["CT"]
    return ResultDataset(ds)


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


def test_volume_path_uses_year_month_and_subject_id():
    base_dir = Path("/tmp/base")
    study_dt = datetime(2024, 2, 15, 10, 30)
    path = _volume_path(base_dir, study_dt, "subject", "1-Head")

    assert path == base_dir / "202402" / "subject" / "1-Head"


# ---------------------------------------------------------------------------
# _find_studies tests
# ---------------------------------------------------------------------------


def _make_processor(mocker: MockerFixture, settings) -> MassTransferTaskProcessor:
    """Create a MassTransferTaskProcessor with a mocked task (no DB required)."""
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = getattr(
        settings, "MASS_TRANSFER_MAX_SEARCH_RESULTS", 200
    )
    mock_task = mocker.MagicMock(spec=MassTransferTask)
    mock_task._meta = MassTransferTask._meta
    # Bypass the isinstance assertion in __init__
    mocker.patch.object(MassTransferTaskProcessor, "__init__", return_value=None)
    processor = MassTransferTaskProcessor.__new__(MassTransferTaskProcessor)
    processor.dicom_task = mock_task
    processor.mass_task = mock_task
    return processor


def _make_filter(mocker: MockerFixture, **kwargs) -> MassTransferFilter:
    """Create a mock MassTransferFilter (no DB required)."""
    mf = mocker.MagicMock(spec=MassTransferFilter)
    mf.modality = kwargs.get("modality", "CT")
    mf.study_description = kwargs.get("study_description", "")
    mf.institution_name = kwargs.get("institution_name", "")
    mf.apply_institution_on_study = kwargs.get("apply_institution_on_study", True)
    mf.series_description = kwargs.get("series_description", "")
    mf.series_number = kwargs.get("series_number", None)
    return mf


def test_find_studies_returns_all_when_under_limit(mocker: MockerFixture, settings):
    """When the PACS returns fewer results than max, return them directly."""
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 10

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="CT")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 23, 59, 59)

    studies = [_make_study("1.2.3"), _make_study("1.2.4"), _make_study("1.2.5")]

    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.return_value = studies

    result = processor._find_studies(operator, mf, start, end)

    assert len(result) == 3
    assert operator.find_studies.call_count == 1


def test_find_studies_splits_and_deduplicates(mocker: MockerFixture, settings):
    """When results exceed max, _find_studies splits the window and deduplicates
    studies that appear in both halves (same-day split)."""
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 2

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="CT")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 2, 23, 59, 59)

    study_a = _make_study("1.2.100")
    study_b = _make_study("1.2.200")
    study_c = _make_study("1.2.300")
    # A duplicate of study_a that would appear in the right half too
    study_a_dup = _make_study("1.2.100")

    # First call: too many results (3 > max=2), triggers split
    # Left half: returns [study_a, study_b] (under limit)
    # Right half: returns [study_a_dup, study_c] (under limit)
    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.side_effect = [
        [study_a, study_b, study_c],  # initial call — over limit
        [study_a, study_b],  # left half
        [study_a_dup, study_c],  # right half
    ]

    result = processor._find_studies(operator, mf, start, end)

    result_uids = [str(s.StudyInstanceUID) for s in result]
    assert len(result) == 3
    assert result_uids.count("1.2.100") == 1, "Duplicate study should be removed"
    assert "1.2.200" in result_uids
    assert "1.2.300" in result_uids


def test_find_studies_split_boundaries_dont_overlap(mocker: MockerFixture, settings):
    """Verify that the left and right halves of a split use non-overlapping time ranges."""
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 1

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 3, 23, 59, 59)

    # Track all (start, end) pairs passed to _find_studies
    call_ranges: list[tuple[datetime, datetime]] = []

    original_find_studies = MassTransferTaskProcessor._find_studies

    def tracking_find_studies(self_inner, operator, mf, s, e):
        call_ranges.append((s, e))
        return original_find_studies(self_inner, operator, mf, s, e)

    # First call: over limit, triggers split
    # Sub-calls: under limit, return single study each
    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.side_effect = [
        [_make_study("1"), _make_study("2")],  # initial — over limit
        [_make_study("1")],  # left half
        [_make_study("2")],  # right half
    ]

    mocker.patch.object(
        MassTransferTaskProcessor,
        "_find_studies",
        side_effect=lambda self_inner, op, mf, s, e: tracking_find_studies(
            self_inner, op, mf, s, e
        ),
        autospec=True,
    )

    processor._find_studies(operator, mf, start, end)

    # We expect 3 calls: the original + 2 recursive halves
    assert len(call_ranges) == 3
    _, _ = call_ranges[0]
    left_start, left_end = call_ranges[1]
    right_start, right_end = call_ranges[2]

    assert left_start == start
    # The right half must start strictly after the left half ends
    assert right_start > left_end


def test_find_studies_preserves_order_with_unique_studies(mocker: MockerFixture, settings):
    """Left-half studies come first, then unique right-half studies are appended."""
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 2

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 3, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.side_effect = [
        # Initial: over limit (3 > 2)
        [_make_study("1.2.1"), _make_study("1.2.2"), _make_study("1.2.3")],
        # Left half: within limit
        [_make_study("1.2.1"), _make_study("1.2.2")],
        # Right half: 1.2.2 is duplicate, 1.2.3 is new
        [_make_study("1.2.2"), _make_study("1.2.3")],
    ]

    result = processor._find_studies(operator, mf, start, end)

    result_uids = [str(s.StudyInstanceUID) for s in result]
    # Left-half results come first, then unique right-half additions
    assert result_uids == ["1.2.1", "1.2.2", "1.2.3"]
    assert len(result) == 3
