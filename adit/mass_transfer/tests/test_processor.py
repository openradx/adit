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
    DiscoveredSeries,
    MassTransferTaskProcessor,
    _dicom_match,
    _parse_int,
    _series_folder_name,
    _study_datetime,
    _study_folder_name,
)


def _make_study(study_uid: str, study_date: str = "20240101") -> ResultDataset:
    ds = Dataset()
    ds.StudyInstanceUID = study_uid
    ds.StudyDate = study_date
    ds.StudyTime = "120000"
    ds.PatientID = "PAT1"
    ds.ModalitiesInStudy = ["CT"]
    return ResultDataset(ds)


def _make_discovered(
    *,
    patient_id: str = "PAT1",
    study_uid: str = "study-1",
    series_uid: str = "series-1",
    modality: str = "CT",
    study_description: str = "Brain CT",
    series_description: str = "Axial",
    series_number: int | None = 1,
    study_datetime: datetime | None = None,
) -> DiscoveredSeries:
    return DiscoveredSeries(
        patient_id=patient_id,
        accession_number="ACC001",
        study_instance_uid=study_uid,
        series_instance_uid=series_uid,
        modality=modality,
        study_description=study_description,
        series_description=series_description,
        series_number=series_number,
        study_datetime=study_datetime or datetime(2024, 1, 1, 12, 0),
        institution_name="Radiology",
        number_of_images=10,
    )


# ---------------------------------------------------------------------------
# _find_studies tests
# ---------------------------------------------------------------------------


def _make_processor(mocker: MockerFixture, settings) -> MassTransferTaskProcessor:
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = getattr(
        settings, "MASS_TRANSFER_MAX_SEARCH_RESULTS", 200
    )
    mock_task = mocker.MagicMock(spec=MassTransferTask)
    mock_task._meta = MassTransferTask._meta
    mocker.patch.object(MassTransferTaskProcessor, "__init__", return_value=None)
    processor = MassTransferTaskProcessor.__new__(MassTransferTaskProcessor)
    processor.dicom_task = mock_task
    processor.mass_task = mock_task
    return processor


def _make_filter(mocker: MockerFixture, **kwargs) -> MassTransferFilter:
    mf = mocker.MagicMock(spec=MassTransferFilter)
    mf.modality = kwargs.get("modality", "CT")
    mf.study_description = kwargs.get("study_description", "")
    mf.institution_name = kwargs.get("institution_name", "")
    mf.apply_institution_on_study = kwargs.get("apply_institution_on_study", True)
    mf.series_description = kwargs.get("series_description", "")
    mf.series_number = kwargs.get("series_number", None)
    return mf


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


def test_find_studies_returns_all_when_under_limit(mocker: MockerFixture, settings):
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
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 2

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="CT")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 2, 23, 59, 59)

    study_a = _make_study("1.2.100")
    study_b = _make_study("1.2.200")
    study_c = _make_study("1.2.300")
    study_a_dup = _make_study("1.2.100")

    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.side_effect = [
        [study_a, study_b, study_c],
        [study_a, study_b],
        [study_a_dup, study_c],
    ]

    result = processor._find_studies(operator, mf, start, end)

    result_uids = [str(s.StudyInstanceUID) for s in result]
    assert len(result) == 3
    assert result_uids.count("1.2.100") == 1
    assert "1.2.200" in result_uids
    assert "1.2.300" in result_uids


def test_find_studies_split_boundaries_dont_overlap(mocker: MockerFixture, settings):
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 1

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 3, 23, 59, 59)

    call_ranges: list[tuple[datetime, datetime]] = []
    original_find_studies = MassTransferTaskProcessor._find_studies

    def tracking_find_studies(self_inner, operator, mf, s, e):
        call_ranges.append((s, e))
        return original_find_studies(self_inner, operator, mf, s, e)

    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.side_effect = [
        [_make_study("1"), _make_study("2")],
        [_make_study("1")],
        [_make_study("2")],
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

    assert len(call_ranges) == 3
    left_start, left_end = call_ranges[1]
    right_start, right_end = call_ranges[2]

    assert left_start == start
    assert right_start > left_end


def test_find_studies_preserves_order_with_unique_studies(mocker: MockerFixture, settings):
    settings.MASS_TRANSFER_MAX_SEARCH_RESULTS = 2

    processor = _make_processor(mocker, settings)
    mf = _make_filter(mocker, modality="")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 3, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.find_studies.side_effect = [
        [_make_study("1.2.1"), _make_study("1.2.2"), _make_study("1.2.3")],
        [_make_study("1.2.1"), _make_study("1.2.2")],
        [_make_study("1.2.2"), _make_study("1.2.3")],
    ]

    result = processor._find_studies(operator, mf, start, end)

    result_uids = [str(s.StudyInstanceUID) for s in result]
    assert result_uids == ["1.2.1", "1.2.2", "1.2.3"]


# ---------------------------------------------------------------------------
# process() tests — mocked environment
# ---------------------------------------------------------------------------


def _make_process_env(
    mocker: MockerFixture,
    settings,
    tmp_path: Path,
    *,
    convert_to_nifti: bool = False,
    anonymization_mode: str = "pseudonymize",
) -> MassTransferTaskProcessor:
    processor = _make_processor(mocker, settings)

    mock_job = processor.mass_task.job
    mock_job.anonymization_mode = anonymization_mode
    mock_job.should_pseudonymize = anonymization_mode != "none"
    mock_job.should_link = anonymization_mode == "pseudonymize_with_linking"
    mock_job.convert_to_nifti = convert_to_nifti
    mock_job.pseudonym_salt = "test-salt-for-deterministic-pseudonyms"
    mock_job.source.node_type = DicomNode.NodeType.SERVER
    mock_job.source.dicomserver = mocker.MagicMock()
    mock_job.destination.node_type = DicomNode.NodeType.FOLDER
    mock_job.destination.dicomfolder.path = str(tmp_path / "output")
    mock_job.filters.all.return_value = [_make_filter(mocker)]

    processor.mass_task.pk = 42
    processor.mass_task.partition_key = "20240101"

    mocker.patch.object(processor, "is_suspended", return_value=False)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    # Mock DB queries for deferred insertion
    mocker.patch.object(
        MassTransferVolume.objects, "filter",
        return_value=mocker.MagicMock(
            values_list=mocker.MagicMock(return_value=mocker.MagicMock(
                __iter__=lambda self: iter([]),
            )),
            delete=mocker.MagicMock(),
        ),
    )

    return processor


def test_process_reraises_retriable_dicom_error(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(
        processor,
        "_export_series",
        side_effect=RetriableDicomError("PACS connection lost"),
    )

    with pytest.raises(RetriableDicomError, match="PACS connection lost"):
        processor.process()


def test_process_returns_warning_on_partial_failure(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    call_count = {"n": 0}

    def fake_export(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise DicomError("Export failed")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mocker.patch.object(MassTransferVolume.objects, "create")

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "Processed: 1" in result["log"]
    assert "Failed: 1" in result["log"]


def test_process_returns_failure_when_all_fail(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(
        processor, "_export_series", side_effect=DicomError("PACS down")
    )
    mocker.patch.object(MassTransferVolume.objects, "create")

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "Failed: 2" in result["log"]


def test_process_returns_warning_when_suspended(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    mocker.patch.object(processor, "is_suspended", return_value=True)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "suspended" in result["log"].lower()


def test_process_raises_when_source_not_server(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    processor.mass_task.job.source.node_type = DicomNode.NodeType.FOLDER

    with pytest.raises(DicomError, match="source must be a DICOM server"):
        processor.process()


def test_process_raises_when_destination_not_folder(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    processor.mass_task.job.destination.node_type = DicomNode.NodeType.SERVER

    with pytest.raises(DicomError, match="destination must be a DICOM folder"):
        processor.process()


def test_process_returns_failure_when_no_filters(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    processor.mass_task.job.filters.all.return_value = []

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "filter" in result["log"].lower()


def test_process_returns_success_for_empty_partition(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_process_env(mocker, settings, tmp_path)
    mocker.patch.object(processor, "_discover_series", return_value=[])

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    assert "No series found" in result["message"]


def test_process_skips_already_done_series(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Already-processed series (from prior runs) are skipped."""
    processor = _make_process_env(mocker, settings, tmp_path)
    series = [
        _make_discovered(series_uid="s-done"),
        _make_discovered(series_uid="s-new"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    # Mock the DB query to return s-done as already processed
    mock_qs = mocker.MagicMock()
    mock_qs.values_list.return_value = {"s-done"}
    mock_delete_qs = mocker.MagicMock()

    def filter_side_effect(**kwargs):
        if "status__in" in kwargs:
            return mock_qs
        return mock_delete_qs

    mocker.patch.object(MassTransferVolume.objects, "filter", side_effect=filter_side_effect)

    export_calls = []
    def fake_export(*args, **kwargs):
        export_calls.append(1)
    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mocker.patch.object(MassTransferVolume.objects, "create")

    result = processor.process()

    assert len(export_calls) == 1  # only s-new was exported
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_none_mode_uses_patient_id_as_subject(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In 'none' anonymization mode, no pseudonymizer is used."""
    processor = _make_process_env(
        mocker, settings, tmp_path, anonymization_mode="none"
    )
    series = [_make_discovered(patient_id="REAL-PAT-1", series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    export_calls: list[tuple] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        export_calls.append((subject_id, pseudonymizer))

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mocker.patch.object(MassTransferVolume.objects, "create")

    result = processor.process()

    assert len(export_calls) == 1
    subject_id, pseudonymizer = export_calls[0]
    assert subject_id == "REAL-PAT-1"
    assert pseudonymizer is None
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_pseudonymize_mode_same_study_same_pseudonym(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In non-linking mode, series in the same study share a pseudonym."""
    processor = _make_process_env(mocker, settings, tmp_path)
    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    subject_ids: list[str] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        subject_ids.append(subject_id)

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mocker.patch.object(MassTransferVolume.objects, "create")

    processor.process()

    # Same study → same pseudonym
    assert subject_ids[0] == subject_ids[1]
    assert subject_ids[0] != ""
    assert subject_ids[0] != "PAT1"


def test_process_pseudonymize_mode_different_studies_different_pseudonyms(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In non-linking mode, different studies for the same patient get different pseudonyms."""
    processor = _make_process_env(mocker, settings, tmp_path)
    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT1", study_uid="study-B", series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    subject_ids: list[str] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        subject_ids.append(subject_id)

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mocker.patch.object(MassTransferVolume.objects, "create")

    processor.process()

    # Different studies → different pseudonyms (non-linkable)
    assert subject_ids[0] != subject_ids[1]
    assert subject_ids[0] != ""
    assert subject_ids[0] != "PAT1"


def test_process_linking_mode_uses_deterministic_pseudonym(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """In linking mode, pseudonyms are deterministic (seeded)."""
    processor = _make_process_env(
        mocker, settings, tmp_path, anonymization_mode="pseudonymize_with_linking"
    )
    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    subject_ids: list[str] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        subject_ids.append(subject_id)

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mocker.patch.object(MassTransferVolume.objects, "create")

    processor.process()

    assert subject_ids[0] != ""
    assert subject_ids[0] != "PAT1"
    # Pseudonym should be deterministic — running again with same salt gives same result
    from adit.core.utils.pseudonymizer import Pseudonymizer
    expected = Pseudonymizer(seed="test-salt-for-deterministic-pseudonyms").compute_pseudonym("PAT1")
    assert subject_ids[0] == expected


# ---------------------------------------------------------------------------
# _convert_series tests
# ---------------------------------------------------------------------------


def test_convert_series_raises_on_dcm2niix_failure(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_processor(mocker, settings)
    series = _make_discovered(series_uid="1.2.3")

    dicom_dir = tmp_path / "dicom_input"
    dicom_dir.mkdir()
    output_path = tmp_path / "output"

    mock_result = mocker.MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Segmentation fault"
    mock_result.stdout = ""
    mocker.patch(
        "adit.mass_transfer.processors.subprocess.run", return_value=mock_result
    )

    with pytest.raises(DicomError, match="Conversion failed"):
        processor._convert_series(series, dicom_dir, output_path)


def test_convert_series_raises_when_no_nifti_output(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_processor(mocker, settings)
    series = _make_discovered(series_uid="1.2.3")

    dicom_dir = tmp_path / "dicom_input"
    dicom_dir.mkdir()
    output_path = tmp_path / "output"

    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mock_result.stdout = ""
    mocker.patch(
        "adit.mass_transfer.processors.subprocess.run", return_value=mock_result
    )

    with pytest.raises(DicomError, match="no .nii.gz files"):
        processor._convert_series(series, dicom_dir, output_path)


def test_convert_series_skips_non_image_dicom(
    mocker: MockerFixture, settings, tmp_path: Path
):
    processor = _make_processor(mocker, settings)
    series = _make_discovered(series_uid="1.2.3")

    dicom_dir = tmp_path / "dicom_input"
    dicom_dir.mkdir()
    output_path = tmp_path / "output"

    mock_result = mocker.MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "No valid DICOM images were found"
    mock_result.stdout = ""
    mocker.patch(
        "adit.mass_transfer.processors.subprocess.run", return_value=mock_result
    )

    # Should not raise — non-image DICOMs are silently skipped
    processor._convert_series(series, dicom_dir, output_path)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


def test_series_folder_name_with_number_and_description():
    assert _series_folder_name("Head CT", 1, "1.2.3") == "Head CT_1"


def test_series_folder_name_with_no_description():
    assert _series_folder_name("", 1, "1.2.3") == "Undefined_1"


def test_series_folder_name_with_no_number():
    assert _series_folder_name("Head CT", None, "1.2.3.4.5") == "1.2.3.4.5"


def test_study_folder_name_includes_description_date_and_hash():
    name = _study_folder_name("Brain CT", datetime(2024, 1, 15, 10, 30), "1.2.3.4")
    assert name.startswith("Brain CT_20240115_")
    assert len(name.split("_")) == 3
    # Hash part is 4 chars
    assert len(name.split("_")[2]) == 4


def test_study_folder_name_deterministic():
    name1 = _study_folder_name("Brain CT", datetime(2024, 1, 15), "1.2.3.4")
    name2 = _study_folder_name("Brain CT", datetime(2024, 1, 15), "1.2.3.4")
    assert name1 == name2


def test_study_folder_name_different_uid_different_hash():
    name1 = _study_folder_name("Brain CT", datetime(2024, 1, 15), "1.2.3.4")
    name2 = _study_folder_name("Brain CT", datetime(2024, 1, 15), "1.2.3.5")
    assert name1 != name2


def test_parse_int_normal():
    assert _parse_int("42") == 42


def test_parse_int_none_returns_default():
    assert _parse_int(None, default=7) == 7


def test_parse_int_empty_returns_default():
    assert _parse_int("", default=0) == 0


def test_parse_int_garbage_returns_default():
    assert _parse_int("abc", default=None) is None


def test_study_datetime_with_time():
    ds = Dataset()
    ds.StudyDate = "20240115"
    ds.StudyTime = "103000"
    result = _study_datetime(ResultDataset(ds))
    assert result == datetime(2024, 1, 15, 10, 30, 0)


def test_study_datetime_with_midnight():
    ds = Dataset()
    ds.StudyDate = "20240115"
    ds.StudyTime = "000000"
    result = _study_datetime(ResultDataset(ds))
    assert result == datetime(2024, 1, 15, 0, 0, 0)


def test_dicom_match_empty_pattern_matches_anything():
    assert _dicom_match("", "anything") is True
    assert _dicom_match("", None) is True
    assert _dicom_match("", "") is True


def test_dicom_match_none_value_never_matches():
    assert _dicom_match("CT", None) is False


def test_dicom_match_exact():
    assert _dicom_match("CT", "CT") is True
    assert _dicom_match("CT", "MR") is False


def test_dicom_match_wildcard():
    assert _dicom_match("Head*", "Head CT") is True
    assert _dicom_match("Head*", "Foot CT") is False


# ---------------------------------------------------------------------------
# DB integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_creates_volume_records_on_success(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Deferred insertion: volumes are created in DB after successful export."""
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

    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.4.5")]

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(processor, "_export_series")

    assert MassTransferVolume.objects.filter(job=job).count() == 0

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    vol = MassTransferVolume.objects.get(job=job, series_instance_uid="1.2.3.4.5")
    assert vol.status == MassTransferVolume.Status.EXPORTED
    assert vol.patient_id == "PAT1"
    assert vol.task == task


@pytest.mark.django_db
def test_process_creates_error_volume_on_failure(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Failed exports still create a volume record with ERROR status."""
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

    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.4.5")]

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(
        processor, "_export_series", side_effect=DicomError("Export failed")
    )

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    vol = MassTransferVolume.objects.get(job=job, series_instance_uid="1.2.3.4.5")
    assert vol.status == MassTransferVolume.Status.ERROR
    assert "Export failed" in vol.log


@pytest.mark.django_db
def test_process_deletes_error_volumes_on_retry(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """On retry, ERROR volumes from prior runs are deleted so they can be reprocessed."""
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

    # Simulate a prior failed run that left an ERROR volume
    MassTransferVolume.objects.create(
        job=job,
        task=task,
        partition_key="20240101",
        patient_id="PAT1",
        study_instance_uid="study-1",
        series_instance_uid="1.2.3.4.5",
        modality="CT",
        study_description="Brain CT",
        series_description="Axial",
        series_number=1,
        study_datetime=timezone.now(),
        status=MassTransferVolume.Status.ERROR,
        log="Previous failure",
    )

    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.4.5")]

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(processor, "_export_series")

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    # Old ERROR volume deleted, new EXPORTED volume created
    vols = MassTransferVolume.objects.filter(job=job, series_instance_uid="1.2.3.4.5")
    assert vols.count() == 1
    assert vols.first().status == MassTransferVolume.Status.EXPORTED


@pytest.mark.django_db
def test_process_deterministic_pseudonyms_across_partitions(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Same patient gets the same pseudonym across different partitions (linking mode)."""
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

    task1 = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.make_aware(datetime(2024, 1, 1)),
        partition_end=timezone.make_aware(datetime(2024, 1, 1, 23, 59, 59)),
        partition_key="20240101",
    )
    task2 = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.make_aware(datetime(2024, 1, 2)),
        partition_end=timezone.make_aware(datetime(2024, 1, 2, 23, 59, 59)),
        partition_key="20240102",
    )

    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    # Partition 1: PAT1
    series1 = [_make_discovered(
        patient_id="PAT1", study_uid="1.2.3.100", series_uid="1.2.3.100.1",
    )]
    processor1 = MassTransferTaskProcessor(task1)
    mocker.patch.object(processor1, "_discover_series", return_value=series1)
    mocker.patch.object(processor1, "_export_series")
    processor1.process()

    # Partition 2: same PAT1
    series2 = [_make_discovered(
        patient_id="PAT1", study_uid="1.2.3.200", series_uid="1.2.3.200.1",
    )]
    processor2 = MassTransferTaskProcessor(task2)
    mocker.patch.object(processor2, "_discover_series", return_value=series2)
    mocker.patch.object(processor2, "_export_series")
    processor2.process()

    vol1 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.100.1")
    vol2 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.200.1")

    # Linking mode: same patient → same pseudonym across partitions
    assert vol1.pseudonym == vol2.pseudonym
    assert vol1.pseudonym != ""
    assert vol1.pseudonym != "PAT1"


@pytest.mark.django_db
def test_process_pseudonymize_mode_not_linked_across_partitions(
    mocker: MockerFixture, settings, tmp_path: Path
):
    """Non-linking pseudonymize mode: same patient gets different pseudonyms across partitions."""
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
        anonymization_mode=MassTransferJob.AnonymizationMode.PSEUDONYMIZE,
    )
    job.filters.create(owner=user, name="CT Filter", modality="CT")

    task1 = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.make_aware(datetime(2024, 1, 1)),
        partition_end=timezone.make_aware(datetime(2024, 1, 1, 23, 59, 59)),
        partition_key="20240101",
    )
    task2 = MassTransferTask.objects.create(
        job=job,
        source=source,
        partition_start=timezone.make_aware(datetime(2024, 1, 2)),
        partition_end=timezone.make_aware(datetime(2024, 1, 2, 23, 59, 59)),
        partition_key="20240102",
    )

    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    series1 = [_make_discovered(
        patient_id="PAT1", study_uid="1.2.3.100", series_uid="1.2.3.100.1",
    )]
    processor1 = MassTransferTaskProcessor(task1)
    mocker.patch.object(processor1, "_discover_series", return_value=series1)
    mocker.patch.object(processor1, "_export_series")
    processor1.process()

    series2 = [_make_discovered(
        patient_id="PAT1", study_uid="1.2.3.200", series_uid="1.2.3.200.1",
    )]
    processor2 = MassTransferTaskProcessor(task2)
    mocker.patch.object(processor2, "_discover_series", return_value=series2)
    mocker.patch.object(processor2, "_export_series")
    processor2.process()

    vol1 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.100.1")
    vol2 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.200.1")

    # Non-linking mode: same patient should get DIFFERENT random pseudonyms
    assert vol1.pseudonym != ""
    assert vol2.pseudonym != ""
    assert vol1.pseudonym != "PAT1"
    assert vol1.pseudonym != vol2.pseudonym
