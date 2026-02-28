import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.utils import timezone
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomNode
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
from adit.mass_transfer.processors import (
    MassTransferTaskProcessor,
    _dicom_match,
    _parse_int,
    _series_folder_name,
    _study_datetime,
    _volume_path,
)


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
    """All volumes in the same study receive the same pseudonym."""
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
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    vol1 = MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        study_instance_uid="study-1",
        series_instance_uid="series-1",
        modality="CT",
        study_description="",
        series_description="A",
        series_number=1,
        study_datetime=timezone.now(),
    )
    vol2 = MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        study_instance_uid="study-1",
        series_instance_uid="series-2",
        modality="CT",
        study_description="",
        series_description="B",
        series_number=2,
        study_datetime=timezone.now(),
    )

    processor = MassTransferTaskProcessor(task)

    # Mock _find_volumes to return pre-created volumes (skip PACS query)
    mocker.patch.object(processor, "_find_volumes", return_value=[vol1, vol2])
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    export_calls: list[tuple[str, str]] = []

    def fake_export(_, volume, __, pseudonym, **kwargs):
        export_calls.append((volume.series_instance_uid, pseudonym))

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)
    mocker.patch.object(processor, "_convert_volume", return_value=None)

    mocker.patch(
        "adit.mass_transfer.processors.uuid.uuid4",
        return_value=uuid.UUID(int=1),
    )

    result = processor.process()

    pseudonyms_by_series = {series_uid: pseudonym for series_uid, pseudonym in export_calls}
    # Both volumes in the same study should share a pseudonym
    assert pseudonyms_by_series["series-1"] == pseudonyms_by_series["series-2"]
    assert pseudonyms_by_series["series-1"] != ""
    assert result["status"] == MassTransferTask.Status.SUCCESS


@pytest.mark.django_db
def test_process_opt_out_skips_pseudonymization(
    mocker: MockerFixture,
    settings,
    tmp_path: Path,
):
    """When anonymization_mode=NONE, process passes empty pseudonym."""
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
        anonymization_mode=MassTransferJob.AnonymizationMode.NONE,
    )
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    vol = MassTransferVolume.objects.create(
        job=job,
        task=task,
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

    # Mock _find_volumes to return pre-created volume (skip PACS query)
    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    export_calls: list[str] = []

    def fake_export(_, __, ___, pseudonym, **kwargs):
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


# ---------------------------------------------------------------------------
# process() tests (no DB required — fully mocked)
# ---------------------------------------------------------------------------


def _make_process_env(
    mocker: MockerFixture,
    settings,
    tmp_path: Path,
    *,
    convert_to_nifti: bool = False,
    anonymization_mode: str = "pseudonymize",
) -> MassTransferTaskProcessor:
    """Create a processor with a fully mocked job for testing process()."""
    settings.MASS_TRANSFER_EXPORT_BASE_DIR = str(tmp_path / "exports")

    processor = _make_processor(mocker, settings)

    mock_job = processor.mass_task.job
    mock_job.anonymization_mode = anonymization_mode
    mock_job.should_pseudonymize = anonymization_mode != "none"
    mock_job.should_link = anonymization_mode == "pseudonymize_with_linking"
    mock_job.convert_to_nifti = convert_to_nifti
    mock_job.source.node_type = DicomNode.NodeType.SERVER
    mock_job.source.dicomserver = mocker.MagicMock()
    mock_job.destination.node_type = DicomNode.NodeType.FOLDER
    mock_job.destination.dicomfolder.path = str(tmp_path / "output")
    mock_job.filters.all.return_value = [_make_filter(mocker)]

    processor.mass_task.pk = 42
    processor.mass_task.partition_key = "20240101"

    mocker.patch.object(processor, "is_suspended", return_value=False)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    return processor


def _make_mock_volume(
    mocker: MockerFixture,
    *,
    study_uid: str = "study-1",
    series_uid: str = "series-1",
    status: str | None = None,
    pseudonym: str = "",
    task_id: int | None = None,
) -> MassTransferVolume:
    """Create a mock MassTransferVolume for testing process()."""
    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.status = status or MassTransferVolume.Status.PENDING
    vol.study_instance_uid = study_uid
    vol.series_instance_uid = series_uid
    vol.pseudonym = pseudonym
    vol.task_id = task_id
    return vol


def test_process_reraises_retriable_dicom_error(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """RetriableDicomError from _export_volume propagates for Procrastinate retry.

    Proves: RetriableDicomError is not swallowed by the broad except Exception
    handler and propagates out of process() so Procrastinate can retry the task.
    """
    processor = _make_process_env(mocker, settings, tmp_path)
    vol = _make_mock_volume(mocker)

    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mocker.patch.object(
        processor,
        "_export_volume",
        side_effect=RetriableDicomError("PACS connection lost"),
    )
    mocker.patch.object(processor, "_convert_volume")

    with pytest.raises(RetriableDicomError, match="PACS connection lost"):
        processor.process()


def test_process_calls_convert_when_enabled(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """With convert_to_nifti=True, both _export_volume and _convert_volume are called
    and the export uses the intermediate export_base directory.

    Proves: When convert_to_nifti is enabled, both export and convert are called,
    and the export writes to the intermediate directory (not the final destination).
    """
    processor = _make_process_env(mocker, settings, tmp_path, convert_to_nifti=True)
    vol = _make_mock_volume(mocker)

    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mock_export = mocker.patch.object(processor, "_export_volume")
    mock_convert = mocker.patch.object(processor, "_convert_volume")

    result = processor.process()

    assert mock_export.call_count == 1
    assert mock_convert.call_count == 1
    # Export should use export_base (intermediate dir), not output_base
    export_call_base = mock_export.call_args[0][2]
    assert "exports" in str(export_call_base)
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_skips_convert_when_disabled(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """With convert_to_nifti=False, _convert_volume is not called and export
    goes directly to the destination folder.

    Proves: When convert_to_nifti is disabled, _convert_volume is never called
    and the export writes directly to the destination folder.
    """
    processor = _make_process_env(mocker, settings, tmp_path, convert_to_nifti=False)
    vol = _make_mock_volume(mocker)

    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mock_export = mocker.patch.object(processor, "_export_volume")
    mock_convert = mocker.patch.object(processor, "_convert_volume")

    result = processor.process()

    assert mock_export.call_count == 1
    assert mock_convert.call_count == 0
    # Export should go directly to output_base (destination)
    export_call_base = mock_export.call_args[0][2]
    assert "output" in str(export_call_base)
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_counts_already_done_volumes(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Already-processed volumes are counted and skipped on retry.

    Proves: On retry, already-CONVERTED volumes are counted in total_processed
    (not silently skipped) and are not re-exported or re-converted.
    """
    processor = _make_process_env(mocker, settings, tmp_path, convert_to_nifti=True)

    vol_done = _make_mock_volume(
        mocker, series_uid="s-done", status=MassTransferVolume.Status.CONVERTED
    )
    vol_pending = _make_mock_volume(mocker, series_uid="s-pending")

    mocker.patch.object(processor, "_find_volumes", return_value=[vol_done, vol_pending])
    mock_export = mocker.patch.object(processor, "_export_volume")
    mock_convert = mocker.patch.object(processor, "_convert_volume")

    result = processor.process()

    # Only the pending volume should be exported/converted
    assert mock_export.call_count == 1
    assert mock_convert.call_count == 1
    # Both volumes should be counted as processed (1 already done + 1 new)
    assert "Processed: 2" in result["log"]
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_returns_warning_on_partial_failure(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """When some volumes fail, the task status is WARNING.

    Proves: Mixed success/failure returns WARNING status with correct processed
    and failed counts in the log.
    """
    processor = _make_process_env(mocker, settings, tmp_path)

    vol1 = _make_mock_volume(mocker, series_uid="s-1")
    vol2 = _make_mock_volume(mocker, series_uid="s-2")

    mocker.patch.object(processor, "_find_volumes", return_value=[vol1, vol2])

    call_count = {"n": 0}

    def fake_export(op, volume, base, pseudo, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise DicomError("Export failed")

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)
    mocker.patch.object(processor, "_convert_volume")
    mocker.patch.object(processor, "_cleanup_export")

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "Processed: 1" in result["log"]
    assert "Failed: 1" in result["log"]


# ---------------------------------------------------------------------------
# Resumability tests — verify no re-download after outage
# ---------------------------------------------------------------------------


def test_export_volume_skips_fetch_when_already_exported(
    mocker: MockerFixture, settings
):
    """_export_volume returns immediately for EXPORTED volumes — no PACS fetch.

    Proves: _export_volume short-circuits when status=EXPORTED and exported_folder
    is set, so operator.fetch_series is never called — no redundant PACS download.
    """
    processor = _make_processor(mocker, settings)
    operator = mocker.create_autospec(DicomOperator)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.status = MassTransferVolume.Status.EXPORTED
    vol.exported_folder = "/tmp/already/exported"

    processor._export_volume(operator, vol, Path("/tmp/base"), "pseudo")

    operator.fetch_series.assert_not_called()


def test_convert_volume_skips_when_already_converted(
    mocker: MockerFixture, settings
):
    """_convert_volume returns immediately for CONVERTED volumes — no dcm2niix.

    Proves: _convert_volume short-circuits when status=CONVERTED and converted_file
    is set, so subprocess.run (dcm2niix) is never called — no redundant conversion.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.status = MassTransferVolume.Status.CONVERTED
    vol.converted_file = "/tmp/output/result.nii.gz"

    mock_run = mocker.patch("adit.mass_transfer.processors.subprocess.run")

    processor._convert_volume(vol, Path("/tmp/output"), "pseudo")

    mock_run.assert_not_called()


def test_process_resumes_after_outage_without_refetch(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """After an outage, only PENDING volumes trigger a PACS fetch.

    Simulates a crash-and-resume where the task has three volumes in different
    states:
      - PENDING:   needs full processing (export + convert)
      - EXPORTED:  export finished before crash, needs conversion only
      - CONVERTED: fully done, skip entirely

    Proves: Full integration — only PENDING triggers fetch_series (1 call).
    EXPORTED skips re-download but still proceeds to conversion. CONVERTED is
    fully skipped. All 3 volumes are counted as processed.
    """
    processor = _make_process_env(mocker, settings, tmp_path, convert_to_nifti=True)

    vol_pending = _make_mock_volume(mocker, series_uid="s-pending")
    vol_pending.study_datetime = datetime(2024, 1, 15, 10, 30)
    vol_pending.series_number = 1
    vol_pending.series_description = "Head"
    vol_pending.patient_id = "PATIENT1"

    vol_exported = _make_mock_volume(
        mocker, series_uid="s-exported", status=MassTransferVolume.Status.EXPORTED
    )
    vol_exported.exported_folder = str(tmp_path / "already_exported")

    vol_converted = _make_mock_volume(
        mocker, series_uid="s-converted", status=MassTransferVolume.Status.CONVERTED
    )

    mocker.patch.object(
        processor,
        "_find_volumes",
        return_value=[vol_pending, vol_exported, vol_converted],
    )
    # Don't mock _export_volume — let the real early-return guard run
    mocker.patch("adit.mass_transfer.processors.DicomManipulator")
    mock_convert = mocker.patch.object(processor, "_convert_volume")
    mocker.patch(
        "adit.mass_transfer.processors.uuid.uuid4",
        return_value=uuid.UUID(int=42),
    )

    result = processor.process()

    # Get the mock operator that process() instantiated
    import adit.mass_transfer.processors as _proc

    mock_operator = _proc.DicomOperator.return_value

    # Only the PENDING volume should trigger a PACS fetch
    assert mock_operator.fetch_series.call_count == 1
    assert mock_operator.fetch_series.call_args.kwargs["series_uid"] == "s-pending"

    # Conversion should run for PENDING + EXPORTED, not CONVERTED
    assert mock_convert.call_count == 2

    # All 3 volumes counted as processed
    assert "Processed: 3" in result["log"]
    assert result["status"] == MassTransferTask.Status.SUCCESS


# ---------------------------------------------------------------------------
# HIGH: Pseudonym reuse on retry
# ---------------------------------------------------------------------------


def test_process_reuses_existing_pseudonym_on_retry(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """On retry, volumes that already have a pseudonym from a prior run are reused.

    Proves: When a study has a volume with an existing pseudonym (set during a
    previous partial run), process() reuses that pseudonym instead of generating
    a new one — preserving data linkage between series in the same study.
    """
    processor = _make_process_env(mocker, settings, tmp_path, convert_to_nifti=False)

    # vol_done was exported in a prior run and has a pseudonym
    vol_done = _make_mock_volume(
        mocker,
        series_uid="s-done",
        status=MassTransferVolume.Status.EXPORTED,
        pseudonym="existing-pseudo-abc",
    )
    # vol_pending is in the same study but wasn't exported yet
    vol_pending = _make_mock_volume(mocker, series_uid="s-pending", pseudonym="")

    mocker.patch.object(
        processor, "_find_volumes", return_value=[vol_done, vol_pending]
    )

    export_calls: list[tuple[str, str]] = []

    def fake_export(op, volume, base, pseudonym, **kwargs):
        export_calls.append((volume.series_instance_uid, pseudonym))

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)

    # Should NOT be called — uuid should never be generated
    mock_uuid = mocker.patch(
        "adit.mass_transfer.processors.uuid.uuid4",
        return_value=uuid.UUID(int=99),
    )

    result = processor.process()

    # The pending volume should receive the existing pseudonym, not a new one
    assert len(export_calls) == 1
    assert export_calls[0] == ("s-pending", "existing-pseudo-abc")
    mock_uuid.assert_not_called()
    assert result["status"] == MassTransferTask.Status.SUCCESS


# ---------------------------------------------------------------------------
# HIGH: done_status=EXPORTED when convert_to_nifti=False
# ---------------------------------------------------------------------------


def test_process_counts_exported_as_done_when_not_converting(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """With convert_to_nifti=False, EXPORTED is the terminal state.

    Proves: Already-EXPORTED volumes are counted as done (not re-exported)
    when convert_to_nifti is disabled. The done_status logic correctly uses
    EXPORTED instead of CONVERTED.
    """
    processor = _make_process_env(mocker, settings, tmp_path, convert_to_nifti=False)

    vol_done = _make_mock_volume(
        mocker, series_uid="s-done", status=MassTransferVolume.Status.EXPORTED
    )
    vol_pending = _make_mock_volume(mocker, series_uid="s-pending")

    mocker.patch.object(
        processor, "_find_volumes", return_value=[vol_done, vol_pending]
    )
    mock_export = mocker.patch.object(processor, "_export_volume")
    mock_convert = mocker.patch.object(processor, "_convert_volume")

    result = processor.process()

    # Only the pending volume should be exported
    assert mock_export.call_count == 1
    assert mock_convert.call_count == 0
    # Both volumes should be counted as processed
    assert "Processed: 2" in result["log"]
    assert result["status"] == MassTransferTask.Status.SUCCESS


# ---------------------------------------------------------------------------
# HIGH: All-fail → FAILURE
# ---------------------------------------------------------------------------


def test_process_returns_failure_when_all_volumes_fail(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """When every volume fails, the task status is FAILURE.

    Proves: The all-fail branch (total_failed > 0, total_processed == 0)
    returns FAILURE status, distinguishing it from partial failure (WARNING).
    """
    processor = _make_process_env(mocker, settings, tmp_path)

    vol1 = _make_mock_volume(mocker, series_uid="s-1")
    vol2 = _make_mock_volume(mocker, series_uid="s-2")

    mocker.patch.object(processor, "_find_volumes", return_value=[vol1, vol2])
    mocker.patch.object(
        processor, "_export_volume", side_effect=DicomError("PACS down")
    )
    mocker.patch.object(processor, "_cleanup_export")

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "Processed: 0" in result["log"]
    assert "Failed: 2" in result["log"]


# ---------------------------------------------------------------------------
# MEDIUM: process() early guards
# ---------------------------------------------------------------------------


def test_process_returns_warning_when_suspended(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """When the mass transfer app is suspended, process() returns WARNING.

    Proves: The suspended guard fires before any PACS interaction and returns
    a WARNING so the task can be retried later without being marked as failed.
    """
    processor = _make_process_env(mocker, settings, tmp_path)
    # Override the is_suspended mock from _make_process_env
    mocker.patch.object(processor, "is_suspended", return_value=True)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "suspended" in result["log"].lower()


def test_process_raises_when_source_not_server(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Source must be a DICOM server.

    Proves: process() raises DicomError with a clear message when the source
    node is not a SERVER, before any volumes are processed.
    """
    processor = _make_process_env(mocker, settings, tmp_path)
    processor.mass_task.job.source.node_type = DicomNode.NodeType.FOLDER

    with pytest.raises(DicomError, match="source must be a DICOM server"):
        processor.process()


def test_process_raises_when_destination_not_folder(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Destination must be a DICOM folder.

    Proves: process() raises DicomError with a clear message when the destination
    node is not a FOLDER, before any volumes are processed.
    """
    processor = _make_process_env(mocker, settings, tmp_path)
    processor.mass_task.job.destination.node_type = DicomNode.NodeType.SERVER

    with pytest.raises(DicomError, match="destination must be a DICOM folder"):
        processor.process()


def test_process_returns_failure_when_no_filters(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """When no filters are configured, process() returns FAILURE.

    Proves: The no-filters guard returns FAILURE with a clear message instead
    of silently succeeding with zero volumes.
    """
    processor = _make_process_env(mocker, settings, tmp_path)
    processor.mass_task.job.filters.all.return_value = []

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "filter" in result["log"].lower()


def test_process_returns_success_for_empty_partition(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """When no volumes are found, process() returns SUCCESS.

    Proves: An empty partition is a legitimate outcome (not an error). The task
    reports SUCCESS with a "No volumes found" message.
    """
    processor = _make_process_env(mocker, settings, tmp_path)
    mocker.patch.object(processor, "_find_volumes", return_value=[])

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    assert "No volumes found" in result["message"]


# ---------------------------------------------------------------------------
# MEDIUM: _convert_volume error cases
# ---------------------------------------------------------------------------


def test_convert_volume_raises_when_no_exported_folder(
    mocker: MockerFixture, settings
):
    """_convert_volume raises DicomError when exported_folder is empty.

    Proves: The guard at the top of _convert_volume catches a missing
    exported_folder and raises a clear DicomError instead of passing garbage
    to dcm2niix.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.status = MassTransferVolume.Status.EXPORTED
    vol.exported_folder = ""
    vol.converted_file = ""

    with pytest.raises(DicomError, match="Missing exported folder"):
        processor._convert_volume(vol, Path("/tmp/output"), "pseudo")


def test_convert_volume_raises_on_dcm2niix_failure(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """_convert_volume raises DicomError when dcm2niix returns non-zero.

    Proves: A dcm2niix crash produces a clear DicomError with stderr content,
    not a silent pass or uncaught exception.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.status = MassTransferVolume.Status.EXPORTED
    vol.exported_folder = str(tmp_path / "dicom_input")
    vol.converted_file = ""
    vol.series_instance_uid = "1.2.3"
    vol.series_number = 1
    vol.series_description = "Head"
    vol.pseudonym = "pseudo"
    vol.patient_id = "PAT1"
    vol.study_datetime = datetime(2024, 1, 15, 10, 30)

    mock_result = mocker.MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Segmentation fault"
    mocker.patch(
        "adit.mass_transfer.processors.subprocess.run", return_value=mock_result
    )

    with pytest.raises(DicomError, match="Conversion failed"):
        processor._convert_volume(vol, tmp_path / "output", "pseudo")


def test_convert_volume_raises_when_no_nifti_output(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """_convert_volume raises DicomError when dcm2niix produces no .nii.gz files.

    Proves: A successful dcm2niix run that produces no output files is caught
    and raises a clear DicomError instead of silently writing empty metadata.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.status = MassTransferVolume.Status.EXPORTED
    vol.exported_folder = str(tmp_path / "dicom_input")
    vol.converted_file = ""
    vol.series_instance_uid = "1.2.3"
    vol.series_number = 1
    vol.series_description = "Head"
    vol.pseudonym = "pseudo"
    vol.patient_id = "PAT1"
    vol.study_datetime = datetime(2024, 1, 15, 10, 30)

    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mocker.patch(
        "adit.mass_transfer.processors.subprocess.run", return_value=mock_result
    )

    with pytest.raises(DicomError, match="no .nii.gz files"):
        processor._convert_volume(vol, tmp_path / "output", "pseudo")


# ---------------------------------------------------------------------------
# MEDIUM: _cleanup_export tests
# ---------------------------------------------------------------------------


def test_cleanup_export_sets_export_cleaned_flag(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """_cleanup_export removes the folder and sets export_cleaned=True.

    Proves: On success, the export folder is deleted and export_cleaned is
    set so the cleanup is not attempted again on a subsequent call.
    """
    processor = _make_processor(mocker, settings)

    export_dir = tmp_path / "exports" / "202401" / "PATIENT" / "1-Head"
    export_dir.mkdir(parents=True)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.exported_folder = str(export_dir)
    vol.export_cleaned = False

    processor._cleanup_export(vol)

    assert not export_dir.exists()
    assert vol.export_cleaned is True
    vol.save.assert_called()


def test_cleanup_export_skips_when_already_cleaned(
    mocker: MockerFixture, settings
):
    """_cleanup_export is a no-op when export_cleaned is already True.

    Proves: The already-cleaned guard prevents redundant rmtree calls,
    avoiding FileNotFoundError on repeated invocations.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.exported_folder = "/tmp/some/path"
    vol.export_cleaned = True

    mock_rmtree = mocker.patch("adit.mass_transfer.processors.shutil.rmtree")

    processor._cleanup_export(vol)

    mock_rmtree.assert_not_called()
    vol.save.assert_not_called()


def test_cleanup_export_skips_when_no_folder(mocker: MockerFixture, settings):
    """_cleanup_export is a no-op when exported_folder is empty.

    Proves: Volumes that were never exported (empty exported_folder) don't
    trigger any filesystem operations.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.exported_folder = ""
    vol.export_cleaned = False

    mock_rmtree = mocker.patch("adit.mass_transfer.processors.shutil.rmtree")

    processor._cleanup_export(vol)

    mock_rmtree.assert_not_called()
    vol.save.assert_not_called()


def test_cleanup_export_handles_file_not_found(
    mocker: MockerFixture, settings
):
    """_cleanup_export silently passes when the folder is already gone.

    Proves: FileNotFoundError (e.g., another process already cleaned up) is
    caught and the volume is still marked as cleaned.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.exported_folder = "/tmp/already/gone"
    vol.export_cleaned = False

    mocker.patch(
        "adit.mass_transfer.processors.shutil.rmtree",
        side_effect=FileNotFoundError,
    )

    processor._cleanup_export(vol)

    assert vol.export_cleaned is True
    vol.save.assert_called()


def test_cleanup_export_handles_permission_error(
    mocker: MockerFixture, settings
):
    """_cleanup_export logs the error and does NOT set export_cleaned on PermissionError.

    Proves: When rmtree fails with a non-FileNotFoundError (e.g., permissions),
    the error is logged but the task doesn't crash, and export_cleaned stays
    False so cleanup can be reattempted.
    """
    processor = _make_processor(mocker, settings)

    vol = mocker.MagicMock(spec=MassTransferVolume)
    vol.exported_folder = "/tmp/locked/folder"
    vol.export_cleaned = False

    mocker.patch(
        "adit.mass_transfer.processors.shutil.rmtree",
        side_effect=PermissionError("Access denied"),
    )

    processor._cleanup_export(vol)

    # export_cleaned should NOT be set — cleanup needs to be retried
    assert vol.export_cleaned is False
    vol.add_log.assert_called_once()
    assert "Cleanup failed" in vol.add_log.call_args[0][0]


# ---------------------------------------------------------------------------
# LOW: Utility function tests
# ---------------------------------------------------------------------------


def test_series_folder_name_with_number_and_description():
    """Proves: Normal case produces '{number}-{description}' format."""
    assert _series_folder_name(1, "Head CT", "1.2.3") == "1-Head CT"


def test_series_folder_name_with_no_description():
    """Proves: Missing description falls back to 'Undefined'."""
    assert _series_folder_name(1, "", "1.2.3") == "1-Undefined"


def test_series_folder_name_with_no_number():
    """Proves: Missing series_number falls back to the series UID."""
    assert _series_folder_name(None, "Head CT", "1.2.3.4.5") == "1.2.3.4.5"


def test_parse_int_normal():
    """Proves: String integers are parsed correctly."""
    assert _parse_int("42") == 42


def test_parse_int_none_returns_default():
    """Proves: None returns the specified default."""
    assert _parse_int(None, default=7) == 7


def test_parse_int_empty_returns_default():
    """Proves: Empty string returns the specified default."""
    assert _parse_int("", default=0) == 0


def test_parse_int_garbage_returns_default():
    """Proves: Non-numeric strings return the default instead of raising."""
    assert _parse_int("abc", default=None) is None


def test_study_datetime_with_time():
    """Proves: StudyDate + StudyTime are combined into a datetime."""
    ds = Dataset()
    ds.StudyDate = "20240115"
    ds.StudyTime = "103000"
    result = _study_datetime(ResultDataset(ds))
    assert result == datetime(2024, 1, 15, 10, 30, 0)


def test_study_datetime_with_midnight():
    """Proves: StudyTime of "000000" (midnight) is correctly parsed.

    Note: The `if study_time is None` guard in _study_datetime is dead code —
    ResultDataset.StudyTime always passes through convert_to_python_time() which
    asserts on both None and empty string before the guard can fire. If PACS
    returns a study with no StudyTime, the crash happens in the converter, not
    in _study_datetime. Consider fixing convert_to_python_time to return
    time(0,0) for None/empty, or catching it in _study_datetime.
    """
    ds = Dataset()
    ds.StudyDate = "20240115"
    ds.StudyTime = "000000"
    result = _study_datetime(ResultDataset(ds))
    assert result == datetime(2024, 1, 15, 0, 0, 0)


def test_dicom_match_empty_pattern_matches_anything():
    """Proves: An empty pattern matches any value (wildcard behavior)."""
    assert _dicom_match("", "anything") is True
    assert _dicom_match("", None) is True
    assert _dicom_match("", "") is True


def test_dicom_match_none_value_never_matches():
    """Proves: A non-empty pattern never matches None."""
    assert _dicom_match("CT", None) is False


def test_dicom_match_exact():
    """Proves: An exact pattern matches its value."""
    assert _dicom_match("CT", "CT") is True
    assert _dicom_match("CT", "MR") is False


def test_dicom_match_wildcard():
    """Proves: DICOM wildcard patterns (converted to regex) work correctly."""
    # DICOM uses * as wildcard, which should be converted to regex .*
    assert _dicom_match("Head*", "Head CT") is True
    assert _dicom_match("Head*", "Foot CT") is False


# ---------------------------------------------------------------------------
# Anonymization mode tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_linking_mode_creates_associations(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In linking mode, MassTransferAssociation records are created per study."""
    from adit.mass_transfer.models import MassTransferAssociation

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
        anonymization_mode=MassTransferJob.AnonymizationMode.PSEUDONYMIZE_WITH_LINKING,
    )
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    vol = MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        patient_id="PAT1",
        study_instance_uid="1.2.3.4",
        series_instance_uid="1.2.3.4.5",
        modality="CT",
        study_description="",
        series_description="Head",
        series_number=1,
        study_datetime=timezone.now(),
    )

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    def fake_export(op, volume, base, pseudonym, **kwargs):
        volume.status = MassTransferVolume.Status.EXPORTED
        volume.pseudonym = pseudonym
        volume.save()

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)

    mocker.patch(
        "adit.mass_transfer.processors.uuid.uuid4",
        return_value=uuid.UUID(int=1),
    )

    result = processor.process()

    assocs = MassTransferAssociation.objects.filter(job=job)
    assert assocs.count() == 1
    assoc = assocs.first()
    assert assoc.original_study_instance_uid == "1.2.3.4"
    assert assoc.pseudonym == uuid.UUID(int=1).hex
    assert assoc.patient_id == "PAT1"
    assert assoc.pseudonymized_study_instance_uid != ""
    assert result["status"] == MassTransferTask.Status.SUCCESS


@pytest.mark.django_db
def test_process_linking_mode_skips_association_for_failed_study(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In linking mode, no association is created if all volumes in a study failed."""
    from adit.mass_transfer.models import MassTransferAssociation

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
        anonymization_mode=MassTransferJob.AnonymizationMode.PSEUDONYMIZE_WITH_LINKING,
    )
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    vol = MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        patient_id="PAT1",
        study_instance_uid="1.2.3.4",
        series_instance_uid="1.2.3.4.5",
        modality="CT",
        study_description="",
        series_description="Head",
        series_number=1,
        study_datetime=timezone.now(),
    )

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    def fake_export_failure(op, volume, base, pseudonym, **kwargs):
        raise RuntimeError("DICOM export failed")

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export_failure)

    mocker.patch(
        "adit.mass_transfer.processors.uuid.uuid4",
        return_value=uuid.UUID(int=1),
    )

    result = processor.process()

    assert MassTransferAssociation.objects.filter(job=job).count() == 0
    assert result["status"] == MassTransferTask.Status.FAILURE


@pytest.mark.django_db
def test_longitudinal_linking_across_partitions(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Prove that linking mode enables longitudinal tracking across an entire job.

    Scenario:
      - Partition 1 (Jan 1): PAT1/Study-A (2 series), PAT2/Study-B (1 series)
      - Partition 2 (Jan 2): PAT1/Study-C (1 series)

    After processing both partitions:
      - 3 association records exist (one per study)
      - PAT1 has 2 associations → linkable via patient_id
      - PAT2 has 1 association
      - The pseudonymized StudyInstanceUID in each association matches
        what dicognito actually produced during export (probe-anonymize
        consistency)
    """
    from adit.mass_transfer.models import MassTransferAssociation
    from adit.core.utils.pseudonymizer import Pseudonymizer

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
        end_date=date(2024, 1, 2),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        anonymization_mode=MassTransferJob.AnonymizationMode.PSEUDONYMIZE_WITH_LINKING,
    )
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    # --- Partition 1: Jan 1 ---
    task1 = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.make_aware(datetime(2024, 1, 1)),
        partition_end=timezone.make_aware(datetime(2024, 1, 1, 23, 59, 59)),
        partition_key="20240101",
    )

    # PAT1, Study-A, two series
    vol_a1 = MassTransferVolume.objects.create(
        job=job, task=task1, partition_key="20240101",
        patient_id="PAT1",
        study_instance_uid="1.2.840.10001.1.1",
        series_instance_uid="1.2.840.10001.1.1.1",
        modality="CT", study_description="Brain CT",
        series_description="Axial", series_number=1,
        study_datetime=timezone.make_aware(datetime(2024, 1, 1, 10, 0)),
    )
    vol_a2 = MassTransferVolume.objects.create(
        job=job, task=task1, partition_key="20240101",
        patient_id="PAT1",
        study_instance_uid="1.2.840.10001.1.1",
        series_instance_uid="1.2.840.10001.1.1.2",
        modality="CT", study_description="Brain CT",
        series_description="Coronal", series_number=2,
        study_datetime=timezone.make_aware(datetime(2024, 1, 1, 10, 0)),
    )

    # PAT2, Study-B, one series
    vol_b = MassTransferVolume.objects.create(
        job=job, task=task1, partition_key="20240101",
        patient_id="PAT2",
        study_instance_uid="1.2.840.10002.1.1",
        series_instance_uid="1.2.840.10002.1.1.1",
        modality="CT", study_description="Chest CT",
        series_description="Axial", series_number=1,
        study_datetime=timezone.make_aware(datetime(2024, 1, 1, 14, 0)),
    )

    # --- Partition 2: Jan 2 ---
    task2 = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.make_aware(datetime(2024, 1, 2)),
        partition_end=timezone.make_aware(datetime(2024, 1, 2, 23, 59, 59)),
        partition_key="20240102",
    )

    # PAT1 again, Study-C (different study, same patient)
    vol_c = MassTransferVolume.objects.create(
        job=job, task=task2, partition_key="20240102",
        patient_id="PAT1",
        study_instance_uid="1.2.840.10001.1.2",
        series_instance_uid="1.2.840.10001.1.2.1",
        modality="CT", study_description="Follow-up Brain CT",
        series_description="Axial", series_number=1,
        study_datetime=timezone.make_aware(datetime(2024, 1, 2, 9, 0)),
    )

    # --- Capture pseudonymized UIDs produced during export ---
    # Each study's export uses a Pseudonymizer instance. We capture the
    # pseudonymized StudyInstanceUID that dicognito actually produces during
    # the export callback, keyed by original StudyInstanceUID.
    pseudonymized_uids: dict[str, str] = {}

    def fake_export(op, volume, base, pseudonym, *, study_pseudonymizer=None):
        """Fake export that actually runs dicognito on a realistic dataset,
        so we can capture the pseudonymized StudyInstanceUID."""
        if study_pseudonymizer is not None:
            # Build a realistic DICOM dataset and run the pseudonymizer
            ds = Dataset()
            ds.file_meta = Dataset()
            ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
            ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.file_meta.MediaStorageSOPInstanceUID = volume.series_instance_uid
            ds.StudyInstanceUID = volume.study_instance_uid
            ds.SeriesInstanceUID = volume.series_instance_uid
            ds.SOPInstanceUID = volume.series_instance_uid + ".1"
            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.PatientID = volume.patient_id
            ds.PatientName = volume.patient_id
            ds.StudyDate = "20240101"
            ds.StudyTime = "100000"

            study_pseudonymizer.pseudonymize(ds, pseudonym)

            # Capture the pseudonymized StudyInstanceUID (should be the same
            # for all series in the same study sharing the same Anonymizer)
            pseudonymized_uids[volume.study_instance_uid] = str(ds.StudyInstanceUID)

        volume.pseudonym = pseudonym
        volume.status = MassTransferVolume.Status.EXPORTED
        volume.save()

    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    # --- Process partition 1 ---
    processor1 = MassTransferTaskProcessor(task1)
    mocker.patch.object(processor1, "_find_volumes", return_value=[vol_a1, vol_a2, vol_b])
    mocker.patch.object(processor1, "_export_volume", side_effect=fake_export)

    result1 = processor1.process()
    assert result1["status"] == MassTransferTask.Status.SUCCESS

    # --- Process partition 2 ---
    processor2 = MassTransferTaskProcessor(task2)
    mocker.patch.object(processor2, "_find_volumes", return_value=[vol_c])
    mocker.patch.object(processor2, "_export_volume", side_effect=fake_export)

    result2 = processor2.process()
    assert result2["status"] == MassTransferTask.Status.SUCCESS

    # --- Verify association records ---
    assocs = MassTransferAssociation.objects.filter(job=job).order_by(
        "original_study_instance_uid"
    )
    assert assocs.count() == 3  # one per study

    assoc_map = {a.original_study_instance_uid: a for a in assocs}
    assert set(assoc_map.keys()) == {
        "1.2.840.10001.1.1",
        "1.2.840.10002.1.1",
        "1.2.840.10001.1.2",
    }

    # Each association's pseudonymized UID differs from the original
    for assoc in assocs:
        assert assoc.pseudonymized_study_instance_uid != assoc.original_study_instance_uid
        assert assoc.pseudonymized_study_instance_uid != ""

    # Probe-anonymize consistency: the UID in the association table must
    # match what dicognito actually produced during export
    for orig_uid, assoc in assoc_map.items():
        assert orig_uid in pseudonymized_uids, f"No export captured for {orig_uid}"
        assert assoc.pseudonymized_study_instance_uid == pseudonymized_uids[orig_uid], (
            f"Probe UID mismatch for {orig_uid}: "
            f"association={assoc.pseudonymized_study_instance_uid}, "
            f"export={pseudonymized_uids[orig_uid]}"
        )

    # --- Longitudinal linking via patient_id ---
    # PAT1 has studies A and C — we can link them through the association table
    pat1_assocs = [a for a in assocs if a.patient_id == "PAT1"]
    assert len(pat1_assocs) == 2
    pat1_studies = {a.original_study_instance_uid for a in pat1_assocs}
    assert pat1_studies == {"1.2.840.10001.1.1", "1.2.840.10001.1.2"}

    # Their pseudonymized UIDs are different (different studies)
    pat1_pseudo_uids = {a.pseudonymized_study_instance_uid for a in pat1_assocs}
    assert len(pat1_pseudo_uids) == 2

    # PAT2 has only study B
    pat2_assocs = [a for a in assocs if a.patient_id == "PAT2"]
    assert len(pat2_assocs) == 1
    assert pat2_assocs[0].original_study_instance_uid == "1.2.840.10002.1.1"

    # Associations are tied to the correct tasks
    assoc_a = assoc_map["1.2.840.10001.1.1"]
    assoc_b = assoc_map["1.2.840.10002.1.1"]
    assoc_c = assoc_map["1.2.840.10001.1.2"]
    assert assoc_a.task_id == task1.pk
    assert assoc_b.task_id == task1.pk
    assert assoc_c.task_id == task2.pk


@pytest.mark.django_db
def test_process_pseudonymize_mode_no_associations(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In pseudonymize mode (without linking), no associations are created."""
    from adit.mass_transfer.models import MassTransferAssociation

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
        anonymization_mode=MassTransferJob.AnonymizationMode.PSEUDONYMIZE,
    )
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.now(),
        partition_end=timezone.now(),
        partition_key="20240101",
    )

    vol = MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        patient_id="PAT1",
        study_instance_uid="1.2.3.4",
        series_instance_uid="1.2.3.4.5",
        modality="CT",
        study_description="",
        series_description="Head",
        series_number=1,
        study_datetime=timezone.now(),
    )

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_find_volumes", return_value=[vol])
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    def fake_export(op, volume, base, pseudonym, **kwargs):
        volume.status = MassTransferVolume.Status.EXPORTED
        volume.pseudonym = pseudonym
        volume.save()

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)

    result = processor.process()

    assert MassTransferAssociation.objects.filter(job=job).count() == 0
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_none_mode_skips_pseudonymizer(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In 'none' anonymization mode, no pseudonym is generated and no pseudonymizer is created."""
    processor = _make_process_env(
        mocker, settings, tmp_path, anonymization_mode="none"
    )
    vol = _make_mock_volume(mocker, series_uid="s-1")

    mocker.patch.object(processor, "_find_volumes", return_value=[vol])

    export_calls: list[tuple[str, object]] = []

    def fake_export(op, volume, base, pseudonym, **kwargs):
        export_calls.append((pseudonym, kwargs.get("study_pseudonymizer")))

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)

    result = processor.process()

    assert len(export_calls) == 1
    pseudonym, study_pseudonymizer = export_calls[0]
    assert pseudonym == ""
    assert study_pseudonymizer is None
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_pseudonymize_mode_creates_per_study_pseudonymizer(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In pseudonymize mode, a Pseudonymizer is created per study and shared across volumes."""
    from adit.core.utils.pseudonymizer import Pseudonymizer

    processor = _make_process_env(mocker, settings, tmp_path)

    vol1 = _make_mock_volume(mocker, study_uid="study-A", series_uid="s-1")
    vol2 = _make_mock_volume(mocker, study_uid="study-A", series_uid="s-2")
    vol3 = _make_mock_volume(mocker, study_uid="study-B", series_uid="s-3")

    mocker.patch.object(processor, "_find_volumes", return_value=[vol1, vol2, vol3])

    pseudonymizer_ids: list[int | None] = []

    def fake_export(op, volume, base, pseudonym, **kwargs):
        ps = kwargs.get("study_pseudonymizer")
        pseudonymizer_ids.append(id(ps) if ps else None)

    mocker.patch.object(processor, "_export_volume", side_effect=fake_export)

    result = processor.process()

    # Two volumes in study-A share the same Pseudonymizer instance
    assert pseudonymizer_ids[0] is not None
    assert pseudonymizer_ids[0] == pseudonymizer_ids[1]
    # Volume in study-B gets a different Pseudonymizer instance
    assert pseudonymizer_ids[2] is not None
    assert pseudonymizer_ids[2] != pseudonymizer_ids[0]
    assert result["status"] == MassTransferTask.Status.SUCCESS
