from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.utils import timezone
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.models import DicomNode
from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.mass_transfer.models import (
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)
from adit.mass_transfer.processors import (
    DiscoveredSeries,
    FilterSpec,
    MassTransferTaskProcessor,
    _age_at_study,
    _birth_date_range,
    _destination_base_dir,
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


def _fake_export_success(*args, **kwargs):
    """Stub for _export_series that simulates a successful single-image export."""
    return (1, "", "")


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


def _make_processor(mocker: MockerFixture) -> MassTransferTaskProcessor:
    mock_task = mocker.MagicMock(spec=MassTransferTask)
    mock_task._meta = MassTransferTask._meta
    mocker.patch.object(MassTransferTaskProcessor, "__init__", return_value=None)
    processor = MassTransferTaskProcessor.__new__(MassTransferTaskProcessor)
    processor.dicom_task = mock_task
    processor.mass_task = mock_task
    return processor


def _make_filter(**kwargs) -> FilterSpec:
    return FilterSpec(
        modality=kwargs.get("modality", "CT"),
        study_description=kwargs.get("study_description", ""),
        institution_name=kwargs.get("institution_name", ""),
        apply_institution_on_study=kwargs.get("apply_institution_on_study", True),
        series_description=kwargs.get("series_description", ""),
        series_number=kwargs.get("series_number", None),
        min_age=kwargs.get("min_age", None),
        max_age=kwargs.get("max_age", None),
        min_number_of_series_related_instances=kwargs.get(
            "min_number_of_series_related_instances", None
        ),
    )


@pytest.fixture
def mass_transfer_env(tmp_path):
    """Common setup for DB integration tests: settings, user, source, folder dest, job, task."""
    MassTransferSettings.objects.create()
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        pseudonymize=False,
        pseudonym_salt="",
    )
    job.filters_json = [{"modality": "CT"}]
    job.save(update_fields=["filters_json"])
    now = timezone.now()
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=now,
        partition_end=now + timedelta(hours=23, minutes=59, seconds=59),
        partition_key="20240101",
    )
    return SimpleNamespace(job=job, task=task, source=source, destination=destination, user=user)


@pytest.mark.django_db
def test_find_studies_raises_when_time_window_too_small(mocker: MockerFixture):
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create(max_search_results=1)
    destination = DicomFolderFactory.create()
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )
    job.filters_json = [{"modality": "CT"}]
    job.save(update_fields=["filters_json"])

    start = timezone.now()
    end = start + timedelta(minutes=10)
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=start,
        partition_end=end,
        partition_key="20240101",
    )

    processor = MassTransferTaskProcessor(task)
    operator = mocker.create_autospec(DicomOperator)
    operator.server = source
    operator.find_studies.return_value = [object(), object()]

    mf = FilterSpec(modality="CT")
    with pytest.raises(DicomError, match="Time window too small"):
        processor._find_studies(operator, mf, start, end)


def test_find_studies_returns_all_when_under_limit(mocker: MockerFixture):
    processor = _make_processor(mocker)
    mf = _make_filter(modality="CT")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 23, 59, 59)

    studies = [_make_study("1.2.3"), _make_study("1.2.4"), _make_study("1.2.5")]

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=10)
    operator.find_studies.return_value = studies

    result = processor._find_studies(operator, mf, start, end)

    assert len(result) == 3
    assert operator.find_studies.call_count == 1


def test_find_studies_splits_and_deduplicates(mocker: MockerFixture):
    processor = _make_processor(mocker)
    mf = _make_filter(modality="CT")

    # Use a single-day range to test the time-based midpoint split
    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 23, 59, 59)

    study_a = _make_study("1.2.100")
    study_b = _make_study("1.2.200")
    study_c = _make_study("1.2.300")
    study_a_dup = _make_study("1.2.100")

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=2)
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


def test_find_studies_split_boundaries_dont_overlap(mocker: MockerFixture):
    processor = _make_processor(mocker)
    mf = _make_filter(modality="")

    # Use a single-day range so we test the time-based midpoint split
    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 23, 59, 59)

    call_ranges: list[tuple[datetime, datetime]] = []
    original_find_studies = MassTransferTaskProcessor._find_studies

    def tracking_find_studies(self_inner, operator, mf, s, e):
        call_ranges.append((s, e))
        return original_find_studies(self_inner, operator, mf, s, e)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=1)
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


def test_find_studies_same_day_split_narrows_study_time(mocker: MockerFixture):
    """When splitting within a single day, StudyTime must narrow to avoid infinite recursion."""
    processor = _make_processor(mocker)
    mf = _make_filter(modality="CT")

    start = datetime(2024, 1, 1, 8, 0, 0)
    end = datetime(2024, 1, 1, 20, 0, 0)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=1)
    # First call returns too many results (triggers split), sub-calls return under limit
    operator.find_studies.side_effect = [
        [_make_study("1"), _make_study("2")],
        [_make_study("1")],
        [_make_study("2")],
    ]

    processor._find_studies(operator, mf, start, end)

    # 3 calls: initial + left half + right half
    assert operator.find_studies.call_count == 3

    queries = [call.args[0] for call in operator.find_studies.call_args_list]
    initial_time = queries[0].dataset.StudyTime
    left_time = queries[1].dataset.StudyTime
    right_time = queries[2].dataset.StudyTime

    # Initial query should use the actual start/end times
    assert "080000" in initial_time
    assert "200000" in initial_time

    # Sub-queries should have narrower time ranges than the initial query
    assert left_time != initial_time
    assert right_time != initial_time


def test_find_studies_cross_midnight_splits_at_midnight(mocker: MockerFixture):
    """A cross-midnight window must split at midnight, not at the midpoint."""
    processor = _make_processor(mocker)
    mf = _make_filter(modality="CT")

    # Window spans midnight: Jan 1 23:45 to Jan 2 00:15
    start = datetime(2024, 1, 1, 23, 45, 0)
    end = datetime(2024, 1, 2, 0, 15, 0)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)
    # Two sub-queries: before midnight and after midnight
    operator.find_studies.side_effect = [
        [_make_study("1")],
        [_make_study("2")],
    ]

    result = processor._find_studies(operator, mf, start, end)

    assert len(result) == 2
    assert operator.find_studies.call_count == 2

    # Verify the queries use single-day ranges with proper times
    q1 = operator.find_studies.call_args_list[0].args[0]
    q2 = operator.find_studies.call_args_list[1].args[0]
    assert "234500" in q1.dataset.StudyTime
    assert "235959" in q1.dataset.StudyTime
    assert "000000" in q2.dataset.StudyTime
    assert "001500" in q2.dataset.StudyTime


def test_find_studies_preserves_order_with_unique_studies(mocker: MockerFixture):
    processor = _make_processor(mocker)
    mf = _make_filter(modality="")

    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=2)
    operator.find_studies.side_effect = [
        [_make_study("1.2.1"), _make_study("1.2.2"), _make_study("1.2.3")],
        [_make_study("1.2.1"), _make_study("1.2.2")],
        [_make_study("1.2.2"), _make_study("1.2.3")],
    ]

    result = processor._find_studies(operator, mf, start, end)

    result_uids = [str(s.StudyInstanceUID) for s in result]
    assert result_uids == ["1.2.1", "1.2.2", "1.2.3"]


# ---------------------------------------------------------------------------
# _discover_series tests
# ---------------------------------------------------------------------------


def _make_series_result(
    series_uid: str,
    modality: str = "CT",
    series_description: str = "Axial",
    series_number: int = 1,
    institution_name: str = "Radiology",
    num_images: int = 10,
) -> ResultDataset:
    ds = Dataset()
    ds.SeriesInstanceUID = series_uid
    ds.Modality = modality
    ds.SeriesDescription = series_description
    ds.SeriesNumber = series_number
    ds.InstitutionName = institution_name
    ds.NumberOfSeriesRelatedInstances = num_images
    return ResultDataset(ds)


def test_discover_series_filters_by_modality(mocker: MockerFixture):
    processor = _make_processor(mocker)
    processor.mass_task.partition_start = datetime(2024, 1, 1, 0, 0)
    processor.mass_task.partition_end = datetime(2024, 1, 1, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)

    study = _make_study("1.2.3.100")
    study.dataset.ModalitiesInStudy = ["CT", "MR"]
    operator.find_studies.return_value = [study]

    ct_series = _make_series_result("1.2.3.201", modality="CT")
    mr_series = _make_series_result("1.2.3.202", modality="MR")
    operator.find_series.return_value = [ct_series, mr_series]

    # Filter for MR only
    filters = [_make_filter(modality="MR")]
    result = processor._discover_series(operator, filters)

    assert len(result) == 1
    assert result[0].series_instance_uid == "1.2.3.202"


def test_discover_series_deduplicates_across_filters(mocker: MockerFixture):
    processor = _make_processor(mocker)
    processor.mass_task.partition_start = datetime(2024, 1, 1, 0, 0)
    processor.mass_task.partition_end = datetime(2024, 1, 1, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)

    study = _make_study("1.2.3.100")
    study.dataset.ModalitiesInStudy = ["CT"]
    operator.find_studies.return_value = [study]

    series = _make_series_result("1.2.3.301", modality="CT")
    operator.find_series.return_value = [series]

    # Two filters that both match the same series
    filters = [_make_filter(modality="CT"), _make_filter(modality="CT")]
    result = processor._discover_series(operator, filters)

    assert len(result) == 1


def test_discover_series_filters_by_series_description(mocker: MockerFixture):
    processor = _make_processor(mocker)
    processor.mass_task.partition_start = datetime(2024, 1, 1, 0, 0)
    processor.mass_task.partition_end = datetime(2024, 1, 1, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)

    study = _make_study("1.2.3.100")
    study.dataset.ModalitiesInStudy = ["CT"]
    operator.find_studies.return_value = [study]

    axial = _make_series_result("1.2.3.401", series_description="Axial T1")
    sagittal = _make_series_result("1.2.3.402", series_description="Sagittal T2")
    operator.find_series.return_value = [axial, sagittal]

    filters = [_make_filter(modality="CT", series_description="Axial*")]
    result = processor._discover_series(operator, filters)

    assert len(result) == 1
    assert result[0].series_instance_uid == "1.2.3.401"


def test_discover_series_filters_by_min_instances(mocker: MockerFixture):
    processor = _make_processor(mocker)
    processor.mass_task.partition_start = datetime(2024, 1, 1, 0, 0)
    processor.mass_task.partition_end = datetime(2024, 1, 1, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)

    study = _make_study("1.2.3.100")
    study.dataset.ModalitiesInStudy = ["CT"]
    operator.find_studies.return_value = [study]

    big_series = _make_series_result("1.2.3.501", num_images=10)
    small_series = _make_series_result("1.2.3.502", num_images=2)
    operator.find_series.return_value = [big_series, small_series]

    filters = [_make_filter(modality="CT", min_number_of_series_related_instances=5)]
    result = processor._discover_series(operator, filters)

    assert len(result) == 1
    assert result[0].series_instance_uid == "1.2.3.501"


def test_discover_series_no_min_instances_filter_includes_all(mocker: MockerFixture):
    processor = _make_processor(mocker)
    processor.mass_task.partition_start = datetime(2024, 1, 1, 0, 0)
    processor.mass_task.partition_end = datetime(2024, 1, 1, 23, 59, 59)

    operator = mocker.create_autospec(DicomOperator)
    operator.server = mocker.MagicMock(max_search_results=200)

    study = _make_study("1.2.3.100")
    study.dataset.ModalitiesInStudy = ["CT"]
    operator.find_studies.return_value = [study]

    big_series = _make_series_result("1.2.3.501", num_images=10)
    small_series = _make_series_result("1.2.3.502", num_images=2)
    operator.find_series.return_value = [big_series, small_series]

    filters = [_make_filter(modality="CT")]  # no min_number_of_series_related_instances
    result = processor._discover_series(operator, filters)

    assert len(result) == 2


# ---------------------------------------------------------------------------
# process() tests — mocked environment
# ---------------------------------------------------------------------------


def _make_process_env(
    mocker: MockerFixture,
    tmp_path: Path,
    *,
    convert_to_nifti: bool = False,
    pseudonymize: bool = True,
    pseudonym_salt: str = "test-salt-for-deterministic-pseudonyms",
) -> MassTransferTaskProcessor:
    processor = _make_processor(mocker)

    mock_job = processor.mass_task.job
    mock_job.convert_to_nifti = convert_to_nifti
    mock_job.pseudonymize = pseudonymize
    mock_job.pseudonym_salt = pseudonym_salt
    mock_job.filters_json = [{"modality": "CT"}]
    mock_job.get_filters.return_value = [FilterSpec.from_dict({"modality": "CT"})]

    processor.mass_task.source.node_type = DicomNode.NodeType.SERVER
    processor.mass_task.source.dicomserver = mocker.MagicMock()
    processor.mass_task.destination.node_type = DicomNode.NodeType.FOLDER
    processor.mass_task.destination.dicomfolder.path = str(tmp_path / "output")

    processor.mass_task.pk = 42
    processor.mass_task.partition_key = "20240101"

    mocker.patch.object(processor, "is_suspended", return_value=False)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    # Mock DB operations used by the processor
    mocker.patch.object(
        MassTransferVolume.objects,
        "filter",
        return_value=mocker.MagicMock(delete=mocker.MagicMock()),
    )
    mocker.patch.object(
        MassTransferVolume.objects,
        "bulk_create",
        side_effect=lambda objs: objs,
    )
    mocker.patch.object(MassTransferVolume, "save")

    return processor


def _make_process_env_server_dest(
    mocker: MockerFixture,
    *,
    pseudonymize: bool = True,
    pseudonym_salt: str = "test-salt-for-deterministic-pseudonyms",
    dest_operator: MagicMock | None = None,
) -> tuple["MassTransferTaskProcessor", MagicMock]:
    """Set up a processor with a SERVER destination.

    Returns (processor, dest_operator_mock).
    """
    processor = _make_processor(mocker)

    mock_job = processor.mass_task.job
    mock_job.convert_to_nifti = False
    mock_job.pseudonymize = pseudonymize
    mock_job.pseudonym_salt = pseudonym_salt
    mock_job.filters_json = [{"modality": "CT"}]
    mock_job.get_filters.return_value = [FilterSpec.from_dict({"modality": "CT"})]

    processor.mass_task.source.node_type = DicomNode.NodeType.SERVER
    processor.mass_task.source.dicomserver = mocker.MagicMock()
    processor.mass_task.destination.node_type = DicomNode.NodeType.SERVER
    processor.mass_task.destination.dicomserver = mocker.MagicMock()

    processor.mass_task.pk = 42
    processor.mass_task.partition_key = "20240101"

    mocker.patch.object(processor, "is_suspended", return_value=False)

    source_mock = mocker.MagicMock()
    if dest_operator is None:
        dest_operator = mocker.MagicMock()
    # dest DicomOperator is created first, source second
    mocker.patch(
        "adit.mass_transfer.processors.DicomOperator",
        side_effect=[dest_operator, source_mock],
    )

    # Mock DB operations used by the processor
    mocker.patch.object(
        MassTransferVolume.objects,
        "filter",
        return_value=mocker.MagicMock(delete=mocker.MagicMock()),
    )
    mocker.patch.object(
        MassTransferVolume.objects,
        "bulk_create",
        side_effect=lambda objs: objs,
    )
    mocker.patch.object(MassTransferVolume, "save")

    return processor, dest_operator


def test_process_reraises_retriable_dicom_error(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(
        processor,
        "_export_series",
        side_effect=RetriableDicomError("PACS connection lost"),
    )

    with pytest.raises(RetriableDicomError, match="PACS connection lost"):
        processor.process()


def test_process_returns_warning_on_partial_failure(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
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
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "Processed: 1" in result["log"]
    assert "Failed: 1" in result["log"]


def test_process_returns_failure_when_all_fail(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(processor, "_export_series", side_effect=DicomError("PACS down"))

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "Failed: 2" in result["log"]


def test_process_returns_warning_when_suspended(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
    mocker.patch.object(processor, "is_suspended", return_value=True)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.WARNING
    assert "suspended" in result["log"].lower()


def test_process_raises_when_source_not_server(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
    processor.mass_task.source.node_type = DicomNode.NodeType.FOLDER

    with pytest.raises(DicomError, match="source must be a DICOM server"):
        processor.process()


def test_process_returns_failure_when_no_filters(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
    processor.mass_task.job.filters_json = []
    processor.mass_task.job.get_filters.return_value = []

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    assert "filter" in result["log"].lower()


def test_process_returns_success_for_empty_partition(mocker: MockerFixture, tmp_path: Path):
    processor = _make_process_env(mocker, tmp_path)
    mocker.patch.object(processor, "_discover_series", return_value=[])

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    assert "No series found" in result["message"]


def test_process_cleans_partition_on_retry(mocker: MockerFixture, tmp_path: Path):
    """On retry, ALL pre-existing volumes for the partition are deleted and rediscovered."""
    processor = _make_process_env(mocker, tmp_path)
    series = [
        _make_discovered(series_uid="s-1"),
        _make_discovered(series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    # Track the delete call on the volume queryset
    mock_filter_qs = mocker.MagicMock()
    mocker.patch.object(MassTransferVolume.objects, "filter", return_value=mock_filter_qs)

    export_calls = []

    def fake_export(*args, **kwargs):
        export_calls.append(1)
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()

    # All pre-existing volumes for the partition were deleted
    mock_filter_qs.delete.assert_called_once()
    # Both series were exported fresh (no skipping)
    assert len(export_calls) == 2
    assert result["status"] == MassTransferTask.Status.SUCCESS


# ---------------------------------------------------------------------------
# Server destination tests
# ---------------------------------------------------------------------------


def test_process_server_destination_exports_and_uploads(mocker: MockerFixture):
    processor, mock_dest_operator = _make_process_env_server_dest(mocker)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    def fake_export(op, s, path, subject_id, pseudonymizer):
        path.mkdir(parents=True, exist_ok=True)
        (path / "dummy.dcm").write_bytes(b"fake")
        return (1, "pseudo-study-uid", "pseudo-series-uid")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()

    mock_dest_operator.upload_images.assert_called()
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_server_destination_cleans_volumes_on_retry(mocker: MockerFixture):
    """Server destination should still delete old DB volume records on retry."""
    processor, _ = _make_process_env_server_dest(mocker)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    mock_filter_qs = mocker.MagicMock()
    mocker.patch.object(MassTransferVolume.objects, "filter", return_value=mock_filter_qs)

    mocker.patch.object(processor, "_export_series", side_effect=_fake_export_success)

    processor.process()

    mock_filter_qs.delete.assert_called_once()


def test_process_server_destination_closes_dest_operator(mocker: MockerFixture):
    """dest_operator.close() should be called even if transfer fails."""
    processor, mock_dest_operator = _make_process_env_server_dest(mocker)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(processor, "_export_series", side_effect=DicomError("PACS down"))

    processor.process()

    mock_dest_operator.close.assert_called()


def test_export_series_to_server_skips_upload_on_zero_images(mocker: MockerFixture):
    """When _export_series returns 0 images, upload_images must NOT be called."""
    processor = _make_processor(mocker)
    volume = MassTransferVolume(
        series_instance_uid="s-1",
        study_instance_uid="study-1",
        patient_id="PAT1",
        number_of_images=10,
        study_datetime=timezone.now(),
    )
    mock_operator = mocker.MagicMock()
    mock_dest_operator = mocker.MagicMock()

    mocker.patch.object(processor, "_export_series", return_value=(0, "", ""))

    processor._export_series_to_server(mock_operator, volume, None, "subject-1", mock_dest_operator)

    mock_dest_operator.upload_images.assert_not_called()
    assert volume.status == MassTransferVolume.Status.ERROR


def test_export_series_to_server_skips_non_image_series(mocker: MockerFixture):
    """Non-image series (0 instances in PACS) gets SKIPPED, not ERROR."""
    processor = _make_processor(mocker)
    volume = MassTransferVolume(
        series_instance_uid="s-1",
        study_instance_uid="study-1",
        patient_id="PAT1",
        number_of_images=0,
        study_datetime=timezone.now(),
    )
    mock_operator = mocker.MagicMock()
    mock_dest_operator = mocker.MagicMock()

    mocker.patch.object(processor, "_export_series", return_value=(0, "", ""))

    processor._export_series_to_server(mock_operator, volume, None, "subject-1", mock_dest_operator)

    mock_dest_operator.upload_images.assert_not_called()
    assert volume.status == MassTransferVolume.Status.SKIPPED


def test_server_destination_upload_dicom_error_marks_failure(mocker: MockerFixture):
    """When upload_images raises DicomError, the series should be marked as failed."""
    processor, mock_dest_operator = _make_process_env_server_dest(mocker)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    def fake_export(op, s, path, subject_id, pseudonymizer):
        return (1, "pseudo-study-uid", "pseudo-series-uid")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mock_dest_operator.upload_images.side_effect = DicomError("C-STORE rejected")

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE


def test_server_destination_upload_retriable_error_propagates(mocker: MockerFixture):
    """When upload_images raises RetriableDicomError, it must propagate up."""
    processor, mock_dest_operator = _make_process_env_server_dest(mocker)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    def fake_export(op, s, path, subject_id, pseudonymizer):
        return (1, "pseudo-study-uid", "pseudo-series-uid")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)
    mock_dest_operator.upload_images.side_effect = RetriableDicomError("Connection reset")

    with pytest.raises(RetriableDicomError, match="Connection reset"):
        processor.process()


def test_process_none_mode_uses_patient_id_as_subject(mocker: MockerFixture, tmp_path: Path):
    """When pseudonymize=False, no pseudonymizer is used."""
    processor = _make_process_env(mocker, tmp_path, pseudonymize=False, pseudonym_salt="")
    series = [_make_discovered(patient_id="REAL-PAT-1", series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    export_calls: list[tuple] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        export_calls.append((subject_id, pseudonymizer))
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()

    assert len(export_calls) == 1
    subject_id, pseudonymizer = export_calls[0]
    assert subject_id == "REAL-PAT-1"
    assert pseudonymizer is None
    assert result["status"] == MassTransferTask.Status.SUCCESS


def test_process_pseudonymize_mode_same_study_same_pseudonym(mocker: MockerFixture, tmp_path: Path):
    """In non-linking mode, series in the same study share a pseudonym."""
    processor = _make_process_env(mocker, tmp_path, pseudonym_salt="")
    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    subject_ids: list[str] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        subject_ids.append(subject_id)
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    processor.process()

    # Same study → same pseudonym
    assert subject_ids[0] == subject_ids[1]
    assert subject_ids[0] != ""
    assert subject_ids[0] != "PAT1"


def test_process_pseudonymize_mode_different_studies_different_pseudonyms(
    mocker: MockerFixture, tmp_path: Path
):
    """In non-linking mode, different studies for the same patient get different pseudonyms."""
    processor = _make_process_env(mocker, tmp_path, pseudonym_salt="")
    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT1", study_uid="study-B", series_uid="s-2"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    subject_ids: list[str] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        subject_ids.append(subject_id)
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    processor.process()

    # Different studies → different pseudonyms (non-linkable)
    assert subject_ids[0] != subject_ids[1]
    assert subject_ids[0] != ""
    assert subject_ids[0] != "PAT1"


def test_process_linking_mode_uses_deterministic_pseudonym(mocker: MockerFixture, tmp_path: Path):
    """In linking mode (pseudonymize with non-empty salt), pseudonyms are deterministic."""
    processor = _make_process_env(
        mocker, tmp_path, pseudonym_salt="test-salt-for-deterministic-pseudonyms"
    )
    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
    ]

    mocker.patch.object(processor, "_discover_series", return_value=series)

    subject_ids: list[str] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        subject_ids.append(subject_id)
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    processor.process()

    assert subject_ids[0] != ""
    assert subject_ids[0] != "PAT1"
    # Pseudonym should be deterministic — running again with same salt gives same result
    from adit.core.utils.pseudonymizer import compute_pseudonym
    from adit.mass_transfer.processors import _DETERMINISTIC_PSEUDONYM_LENGTH

    expected = compute_pseudonym(
        "test-salt-for-deterministic-pseudonyms",
        "PAT1",
        length=_DETERMINISTIC_PSEUDONYM_LENGTH,
    )
    assert subject_ids[0] == expected


# ---------------------------------------------------------------------------
# _convert_series tests
# ---------------------------------------------------------------------------


def test_convert_series_raises_on_dcm2niix_failure(mocker: MockerFixture, tmp_path: Path):
    processor = _make_processor(mocker)
    volume = MassTransferVolume(series_instance_uid="1.2.3", study_datetime=timezone.now())

    dicom_dir = tmp_path / "dicom_input"
    dicom_dir.mkdir()
    output_path = tmp_path / "output"

    mocker.patch(
        "adit.core.utils.dicom_to_nifti_converter.DicomToNiftiConverter.convert",
        side_effect=RuntimeError("conversion failed"),
    )

    with pytest.raises(DicomError, match="Conversion failed"):
        processor._convert_series(volume, dicom_dir, output_path)


def test_convert_series_raises_when_no_nifti_output(mocker: MockerFixture, tmp_path: Path):
    processor = _make_processor(mocker)
    volume = MassTransferVolume(series_instance_uid="1.2.3", study_datetime=timezone.now())

    dicom_dir = tmp_path / "dicom_input"
    dicom_dir.mkdir()
    output_path = tmp_path / "output"

    # Converter succeeds (does nothing), but output dir has no .nii.gz files
    mocker.patch(
        "adit.core.utils.dicom_to_nifti_converter.DicomToNiftiConverter.convert",
    )

    with pytest.raises(DicomError, match="no .nii.gz files"):
        processor._convert_series(volume, dicom_dir, output_path)


def test_convert_series_skips_non_image_dicom(mocker: MockerFixture, tmp_path: Path):
    processor = _make_processor(mocker)
    volume = MassTransferVolume(series_instance_uid="1.2.3", study_datetime=timezone.now())

    dicom_dir = tmp_path / "dicom_input"
    dicom_dir.mkdir()
    output_path = tmp_path / "output"

    mocker.patch(
        "adit.core.utils.dicom_to_nifti_converter.DicomToNiftiConverter.convert",
        side_effect=RuntimeError("No valid DICOM images were found"),
    )

    # Should not raise — non-image DICOMs are silently skipped
    processor._convert_series(volume, dicom_dir, output_path)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


def test_series_folder_name_with_number_and_description():
    assert _series_folder_name("Head CT", 1, "1.2.3") == "Head CT_1"


def test_series_folder_name_with_no_description():
    assert _series_folder_name("", 1, "1.2.3") == "Undefined_1"


def test_series_folder_name_with_no_number():
    assert _series_folder_name("Head CT", None, "1.2.3.4.5") == "Head CT_1.2.3.4.5"


def test_study_folder_name_includes_description_and_date():
    name = _study_folder_name("Brain CT", datetime(2024, 1, 15, 10, 30))
    assert name == "Brain CT_20240115_103000"


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
def test_process_creates_volume_records_on_success(mocker: MockerFixture, mass_transfer_env):
    """Volumes are created in PENDING then updated to EXPORTED after successful export."""
    env = mass_transfer_env
    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.4.5")]

    processor = MassTransferTaskProcessor(env.task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(processor, "_export_series", side_effect=_fake_export_success)

    assert MassTransferVolume.objects.filter(job=env.job).count() == 0

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    vol = MassTransferVolume.objects.get(job=env.job, series_instance_uid="1.2.3.4.5")
    assert vol.status == MassTransferVolume.Status.EXPORTED
    assert vol.patient_id == "PAT1"
    assert vol.task == env.task


@pytest.mark.django_db
def test_process_creates_error_volume_on_failure(mocker: MockerFixture, mass_transfer_env):
    """Failed exports still create a volume record with ERROR status."""
    env = mass_transfer_env
    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.4.5")]

    processor = MassTransferTaskProcessor(env.task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(processor, "_export_series", side_effect=DicomError("Export failed"))

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.FAILURE
    vol = MassTransferVolume.objects.get(job=env.job, series_instance_uid="1.2.3.4.5")
    assert vol.status == MassTransferVolume.Status.ERROR
    assert "Export failed" in vol.log


@pytest.mark.django_db
def test_process_deletes_all_volumes_on_retry(mocker: MockerFixture, mass_transfer_env):
    """On retry, ALL volumes from prior runs are deleted before rediscovery."""
    env = mass_transfer_env
    job, task = env.job, env.task

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
    mocker.patch.object(processor, "_export_series", side_effect=_fake_export_success)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    # Old ERROR volume deleted, new EXPORTED volume created
    vols = MassTransferVolume.objects.filter(job=job, series_instance_uid="1.2.3.4.5")
    assert vols.count() == 1
    vol = vols.first()
    assert vol is not None
    assert vol.status == MassTransferVolume.Status.EXPORTED


@pytest.mark.django_db
def test_process_deterministic_pseudonyms_across_partitions(mocker: MockerFixture, tmp_path: Path):
    """Same patient gets the same pseudonym across different partitions (linking mode)."""
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        pseudonym_salt="test-salt",
    )
    job.filters_json = [{"modality": "CT"}]
    job.save(update_fields=["filters_json"])

    task1 = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=timezone.make_aware(datetime(2024, 1, 1)),
        partition_end=timezone.make_aware(datetime(2024, 1, 1, 23, 59, 59)),
        partition_key="20240101",
    )
    task2 = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=timezone.make_aware(datetime(2024, 1, 2)),
        partition_end=timezone.make_aware(datetime(2024, 1, 2, 23, 59, 59)),
        partition_key="20240102",
    )

    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    # Partition 1: PAT1
    series1 = [
        _make_discovered(
            patient_id="PAT1",
            study_uid="1.2.3.100",
            series_uid="1.2.3.100.1",
        )
    ]
    processor1 = MassTransferTaskProcessor(task1)
    mocker.patch.object(processor1, "_discover_series", return_value=series1)
    mocker.patch.object(processor1, "_export_series", side_effect=_fake_export_success)
    processor1.process()

    # Partition 2: same PAT1
    series2 = [
        _make_discovered(
            patient_id="PAT1",
            study_uid="1.2.3.200",
            series_uid="1.2.3.200.1",
        )
    ]
    processor2 = MassTransferTaskProcessor(task2)
    mocker.patch.object(processor2, "_discover_series", return_value=series2)
    mocker.patch.object(processor2, "_export_series", side_effect=_fake_export_success)
    processor2.process()

    vol1 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.100.1")
    vol2 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.200.1")

    # Linking mode: same patient → same pseudonym across partitions
    assert vol1.pseudonym == vol2.pseudonym
    assert vol1.pseudonym != ""
    assert vol1.pseudonym != "PAT1"


@pytest.mark.django_db
def test_process_pseudonymize_mode_not_linked_across_partitions(
    mocker: MockerFixture, tmp_path: Path
):
    """Non-linking pseudonymize mode: same patient gets different pseudonyms across partitions."""
    MassTransferSettings.objects.create()

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        pseudonymize=True,
        pseudonym_salt="",
    )
    job.filters_json = [{"modality": "CT"}]
    job.save(update_fields=["filters_json"])

    task1 = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=timezone.make_aware(datetime(2024, 1, 1)),
        partition_end=timezone.make_aware(datetime(2024, 1, 1, 23, 59, 59)),
        partition_key="20240101",
    )
    task2 = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=timezone.make_aware(datetime(2024, 1, 2)),
        partition_end=timezone.make_aware(datetime(2024, 1, 2, 23, 59, 59)),
        partition_key="20240102",
    )

    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    series1 = [
        _make_discovered(
            patient_id="PAT1",
            study_uid="1.2.3.100",
            series_uid="1.2.3.100.1",
        )
    ]
    processor1 = MassTransferTaskProcessor(task1)
    mocker.patch.object(processor1, "_discover_series", return_value=series1)
    mocker.patch.object(processor1, "_export_series", side_effect=_fake_export_success)
    processor1.process()

    series2 = [
        _make_discovered(
            patient_id="PAT1",
            study_uid="1.2.3.200",
            series_uid="1.2.3.200.1",
        )
    ]
    processor2 = MassTransferTaskProcessor(task2)
    mocker.patch.object(processor2, "_discover_series", return_value=series2)
    mocker.patch.object(processor2, "_export_series", side_effect=_fake_export_success)
    processor2.process()

    vol1 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.100.1")
    vol2 = MassTransferVolume.objects.get(series_instance_uid="1.2.3.200.1")

    # Non-linking mode: same patient should get DIFFERENT random pseudonyms
    assert vol1.pseudonym != ""
    assert vol2.pseudonym != ""
    assert vol1.pseudonym != "PAT1"
    assert vol1.pseudonym != vol2.pseudonym


# ---------------------------------------------------------------------------
# Age filtering tests
# ---------------------------------------------------------------------------


def test_age_at_study_basic():
    assert _age_at_study(date(1990, 6, 15), date(2025, 6, 15)) == 35
    assert _age_at_study(date(1990, 6, 15), date(2025, 6, 14)) == 34
    assert _age_at_study(date(1990, 6, 15), date(2025, 6, 16)) == 35


def test_age_at_study_leap_year():
    assert _age_at_study(date(2000, 2, 29), date(2025, 2, 28)) == 24
    assert _age_at_study(date(2000, 2, 29), date(2025, 3, 1)) == 25


def test_birth_date_range_no_age_limits():
    assert _birth_date_range(date(2025, 1, 1), date(2025, 1, 31), None, None) is None


def test_birth_date_range_min_only():
    result = _birth_date_range(date(2025, 3, 15), date(2025, 3, 15), 18, None)
    assert result is not None
    earliest, latest = result
    # Latest birth: someone who is 18 on study date could be born up to end of year 2008
    assert latest.year >= 2007
    assert earliest == date(1900, 1, 1)


def test_birth_date_range_max_only():
    result = _birth_date_range(date(2025, 3, 15), date(2025, 3, 15), None, 65)
    assert result is not None
    earliest, latest = result
    # Earliest birth: someone who is 65 on study date was born ~1959
    assert earliest.year <= 1960


def test_birth_date_range_both():
    result = _birth_date_range(date(2025, 3, 15), date(2025, 3, 15), 18, 65)
    assert result is not None
    earliest, latest = result
    assert earliest < latest


# ---------------------------------------------------------------------------
# FilterSpec tests
# ---------------------------------------------------------------------------


def test_filter_spec_from_dict():
    d = {
        "modality": "MR",
        "institution_name": "Neuroradiologie",
        "min_age": 18,
        "max_age": 90,
    }
    fs = FilterSpec.from_dict(d)
    assert fs.modality == "MR"
    assert fs.institution_name == "Neuroradiologie"
    assert fs.min_age == 18
    assert fs.max_age == 90
    assert fs.study_description == ""
    assert fs.apply_institution_on_study is True


def test_filter_spec_from_dict_with_min_instances():
    d = {"modality": "CT", "min_number_of_series_related_instances": 5}
    fs = FilterSpec.from_dict(d)
    assert fs.min_number_of_series_related_instances == 5


def test_filter_spec_from_dict_without_min_instances():
    d = {"modality": "CT"}
    fs = FilterSpec.from_dict(d)
    assert fs.min_number_of_series_related_instances is None


# ---------------------------------------------------------------------------
# DICOM metadata tests
# ---------------------------------------------------------------------------


def test_write_dicom_metadata(tmp_path: Path):
    from adit.mass_transfer.processors import _write_dicom_metadata

    fields = {
        "PatientBirthDate": "19900101",
        "PatientSex": "M",
        "PatientAgeAtStudy": "35",
        "StudyDate": "20250315",
        "StudyInstanceUID": "1.2.3.4.5",
        "SeriesInstanceUID": "1.2.3.4.5.6",
        "Modality": "MR",
    }

    _write_dicom_metadata(tmp_path, "T1w_3D_101", fields)

    import json

    metadata = tmp_path / "T1w_3D_101_dicom.json"
    assert metadata.exists()
    result = json.loads(metadata.read_text())
    assert result["PatientBirthDate"] == "19900101"
    assert result["PatientAgeAtStudy"] == "35"
    assert result["StudyInstanceUID"] == "1.2.3.4.5"
    assert result["Modality"] == "MR"


def test_write_dicom_metadata_empty_fields(tmp_path: Path):
    from adit.mass_transfer.processors import _write_dicom_metadata

    _write_dicom_metadata(tmp_path, "series_1", {})

    # No file should be written when fields are empty
    assert not list(tmp_path.glob("*.json"))


def _write_test_dicom(path: Path, **kwargs) -> None:
    """Write a minimal valid DICOM file for testing."""
    import pydicom

    ds = pydicom.Dataset()
    for k, v in kwargs.items():
        setattr(ds, k, v)
    ds.SOPClassUID = kwargs.get("SOPClassUID", "1.2.840.10008.5.1.4.1.1.4")
    ds.SOPInstanceUID = kwargs.get("SOPInstanceUID", "1.2.3.4.5")
    from pydicom.dataset import FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta = file_meta
    pydicom.dcmwrite(str(path), ds, enforce_file_format=True)


def test_extract_dicom_metadata_computes_age(tmp_path: Path):
    """_extract_dicom_metadata should compute PatientAgeAtStudy from birth date and study date."""
    from adit.mass_transfer.processors import _extract_dicom_metadata

    _write_test_dicom(
        tmp_path / "test.dcm",
        PatientBirthDate="19900615",
        PatientSex="M",
        StudyDate="20250615",
        StudyInstanceUID="1.2.3",
        SeriesInstanceUID="1.2.3.4",
        Modality="MR",
    )

    result = _extract_dicom_metadata(tmp_path)
    assert result["PatientAgeAtStudy"] == "35"
    assert result["PatientBirthDate"] == "19900615"
    assert result["PatientSex"] == "M"
    assert result["StudyInstanceUID"] == "1.2.3"


def test_extract_dicom_metadata_pseudonymized_has_no_real_data(tmp_path: Path):
    """When pseudonymization is applied, metadata should contain pseudonymized values,
    not originals.

    This test simulates the post-pseudonymization state: the DICOM files on disk have already
    been anonymized by dicognito + Pseudonymizer before _extract_dicom_metadata runs.
    We verify the metadata contains only the pseudonymized values.
    """
    from adit.mass_transfer.processors import _extract_dicom_metadata

    _write_test_dicom(
        tmp_path / "test.dcm",
        PatientID="ABCDEF123456",
        PatientName="ABCDEF123456",
        PatientBirthDate="19920101",
        PatientSex="M",
        StudyDate="20260101",
        StudyInstanceUID="2.25.999999999",
        SeriesInstanceUID="2.25.888888888",
        Modality="MR",
    )

    result = _extract_dicom_metadata(tmp_path)

    # Metadata must contain the pseudonymized values (what's on disk)
    assert result["PatientID"] == "ABCDEF123456"
    assert result["PatientBirthDate"] == "19920101"
    assert result["StudyInstanceUID"] == "2.25.999999999"
    assert result["SeriesInstanceUID"] == "2.25.888888888"
    assert result["StudyDate"] == "20260101"

    # Real values must NOT appear anywhere
    real_patient_id = "4654954"
    real_birth_date = "19900615"
    real_study_uid = "1.2.276.0.18.14.200.2.0.0.2.20250311.175028.78.91"
    for val in result.values():
        assert real_patient_id not in val
        assert real_birth_date not in val
        assert real_study_uid not in val


# ---------------------------------------------------------------------------
# _create_pending_volumes / _group_volumes tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_pending_volumes_deterministic_pseudonym():
    """Seeded pseudonymizer with salt: volumes get deterministic pseudonyms."""
    from adit.core.utils.pseudonymizer import Pseudonymizer

    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        pseudonym_salt="test-seed-123",
    )
    job.filters_json = [{"modality": "CT"}]
    job.save(update_fields=["filters_json"])

    now = timezone.now()
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=now,
        partition_end=now + timedelta(hours=23, minutes=59, seconds=59),
        partition_key="20240101",
    )

    from adit.core.utils.pseudonymizer import compute_pseudonym
    from adit.mass_transfer.processors import _DETERMINISTIC_PSEUDONYM_LENGTH

    ps = Pseudonymizer(seed="test-seed-123")
    expected_pat1 = compute_pseudonym(
        "test-seed-123", "PAT1", length=_DETERMINISTIC_PSEUDONYM_LENGTH
    )
    expected_pat2 = compute_pseudonym(
        "test-seed-123", "PAT2", length=_DETERMINISTIC_PSEUDONYM_LENGTH
    )

    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT2", study_uid="study-B", series_uid="s-2"),
    ]

    processor = MassTransferTaskProcessor(task)
    volumes = processor._create_pending_volumes(series, job, ps)

    assert len(volumes) == 2
    assert volumes[0].pseudonym == expected_pat1
    assert volumes[1].pseudonym == expected_pat2
    assert all(v.status == MassTransferVolume.Status.PENDING for v in volumes)
    assert all(v.pk is not None for v in volumes)

    grouped = MassTransferTaskProcessor._group_volumes(volumes)
    assert "PAT1" in grouped
    assert "PAT2" in grouped


def test_create_pending_volumes_no_anonymization(mocker: MockerFixture):
    """Without pseudonymizer, volumes have empty pseudonym."""
    processor = _make_processor(mocker)
    mocker.patch.object(
        MassTransferVolume.objects,
        "bulk_create",
        side_effect=lambda objs: objs,
    )

    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT2", study_uid="study-B", series_uid="s-2"),
    ]

    mock_job = mocker.MagicMock()
    mock_job.pseudonym_salt = ""

    volumes = processor._create_pending_volumes(series, mock_job, None)

    assert volumes[0].pseudonym == ""
    assert volumes[1].pseudonym == ""


def test_create_pending_volumes_random_assigns_per_study(mocker: MockerFixture):
    """With pseudonymizer but no salt, volumes get per-study random pseudonyms."""
    from adit.core.utils.pseudonymizer import Pseudonymizer

    processor = _make_processor(mocker)
    mocker.patch.object(
        MassTransferVolume.objects,
        "bulk_create",
        side_effect=lambda objs: objs,
    )

    ps = Pseudonymizer()

    mock_job = mocker.MagicMock()
    mock_job.pseudonym_salt = ""

    series = [
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-1"),
        _make_discovered(patient_id="PAT1", study_uid="study-A", series_uid="s-2"),
        _make_discovered(patient_id="PAT1", study_uid="study-B", series_uid="s-3"),
    ]

    volumes = processor._create_pending_volumes(series, mock_job, ps)

    # Same study → same pseudonym
    assert volumes[0].pseudonym == volumes[1].pseudonym
    assert volumes[0].pseudonym != ""
    # Different study → different pseudonym
    assert volumes[0].pseudonym != volumes[2].pseudonym
    assert volumes[2].pseudonym != ""


# ---------------------------------------------------------------------------
# _group_volumes tests
# ---------------------------------------------------------------------------


def test_group_volumes_multi_patient_multi_study():
    """Volumes are grouped by patient_id -> study_instance_uid."""
    now = timezone.now()
    v1 = MassTransferVolume(
        patient_id="PAT1",
        study_instance_uid="study-A",
        series_instance_uid="s-1",
        study_datetime=now,
    )
    v2 = MassTransferVolume(
        patient_id="PAT1",
        study_instance_uid="study-A",
        series_instance_uid="s-2",
        study_datetime=now,
    )
    v3 = MassTransferVolume(
        patient_id="PAT1",
        study_instance_uid="study-B",
        series_instance_uid="s-3",
        study_datetime=now,
    )
    v4 = MassTransferVolume(
        patient_id="PAT2",
        study_instance_uid="study-C",
        series_instance_uid="s-4",
        study_datetime=now,
    )

    grouped = MassTransferTaskProcessor._group_volumes([v1, v2, v3, v4])

    assert set(grouped.keys()) == {"PAT1", "PAT2"}
    assert set(grouped["PAT1"].keys()) == {"study-A", "study-B"}
    assert grouped["PAT1"]["study-A"] == [v1, v2]
    assert grouped["PAT1"]["study-B"] == [v3]
    assert grouped["PAT2"]["study-C"] == [v4]


# ---------------------------------------------------------------------------
# RetriableDicomError volume status tests
# ---------------------------------------------------------------------------


def test_retriable_error_saves_volume_as_error(mocker: MockerFixture, tmp_path: Path):
    """RetriableDicomError should save the current volume as ERROR before propagating."""
    processor = _make_process_env(mocker, tmp_path)
    series = [_make_discovered(series_uid="s-1")]

    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch.object(
        processor,
        "_export_series",
        side_effect=RetriableDicomError("PACS connection lost"),
    )

    with pytest.raises(RetriableDicomError):
        processor.process()

    # volume.save() should have been called (via the finally block)
    MassTransferVolume.save.assert_called()


# ---------------------------------------------------------------------------
# Partition cleanup DB integration test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_partition_cleanup_deletes_folder_and_volumes(mocker: MockerFixture, mass_transfer_env):
    """process() deletes the partition folder on disk and all volumes for that partition."""
    env = mass_transfer_env
    job, task, destination = env.job, env.task, env.destination

    # Create pre-existing volumes
    for uid in ["1.2.3.1", "1.2.3.2"]:
        MassTransferVolume.objects.create(
            job=job,
            task=task,
            partition_key="20240101",
            patient_id="PAT1",
            study_instance_uid="study-1",
            series_instance_uid=uid,
            modality="CT",
            study_description="Brain CT",
            series_description="Axial",
            series_number=1,
            study_datetime=timezone.now(),
            status=MassTransferVolume.Status.EXPORTED,
            log="",
        )

    # Create the partition folder with a file in it
    partition_dir = _destination_base_dir(destination, job) / "20240101"
    partition_dir.mkdir(parents=True, exist_ok=True)
    (partition_dir / "some_file.dcm").write_text("dummy")

    assert MassTransferVolume.objects.filter(job=job, partition_key="20240101").count() == 2

    # Mock discovery to return a new series
    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.new")]
    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")
    mocker.patch.object(processor, "_export_series", side_effect=_fake_export_success)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    # Old partition folder was deleted (process recreates it for the new export)
    assert not (partition_dir / "some_file.dcm").exists()
    # Old volumes were deleted, only the new one remains
    vols = MassTransferVolume.objects.filter(job=job, partition_key="20240101")
    assert vols.count() == 1
    vol = vols.first()
    assert vol is not None
    assert vol.series_instance_uid == "1.2.3.new"


# ---------------------------------------------------------------------------
# MassTransferJob.get_filters() tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_filters_from_json():
    """get_filters() returns FilterSpec objects from valid filters_json."""
    user = UserFactory.create()
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )

    # Valid JSON list of filter dicts
    job.filters_json = [
        {"modality": "CT", "min_age": 18},
        {"modality": "MR", "series_description": "T1*"},
    ]
    job.save(update_fields=["filters_json"])

    filters = job.get_filters()
    assert len(filters) == 2
    assert filters[0].modality == "CT"
    assert filters[0].min_age == 18
    assert filters[1].modality == "MR"
    assert filters[1].series_description == "T1*"

    # Empty list
    job.filters_json = []
    job.save(update_fields=["filters_json"])
    assert job.get_filters() == []


@pytest.mark.django_db
def test_get_filters_empty():
    """get_filters() returns [] when filters_json is None."""
    user = UserFactory.create()
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )

    job.filters_json = None
    job.save(update_fields=["filters_json"])
    assert job.get_filters() == []


# ---------------------------------------------------------------------------
# _destination_base_dir tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_destination_base_dir_creates_job_folder(tmp_path: Path):
    """Output dir should include adit_{app}_{pk}_{date}_{owner} parent folder."""
    user = UserFactory.create(username="rghosh")
    destination = DicomFolderFactory.create(path=str(tmp_path))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2025, 3, 16),
        end_date=date(2025, 3, 16),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )

    result = _destination_base_dir(destination, job)

    expected_name = f"adit_mass_transfer_{job.pk}_{job.created.strftime('%Y%m%d')}_rghosh"
    assert result == tmp_path / expected_name
    assert result.is_dir()


@pytest.mark.django_db
def test_destination_base_dir_is_idempotent(tmp_path: Path):
    """Calling _destination_base_dir twice should not fail or create duplicates."""
    user = UserFactory.create(username="testuser")
    destination = DicomFolderFactory.create(path=str(tmp_path))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )

    result1 = _destination_base_dir(destination, job)
    result2 = _destination_base_dir(destination, job)

    assert result1 == result2
    assert result1.is_dir()


def test_destination_base_dir_asserts_on_server_node(mocker: MockerFixture):
    """Should raise AssertionError when node is not a FOLDER."""
    node = mocker.MagicMock()
    node.node_type = DicomNode.NodeType.SERVER
    job = mocker.MagicMock()

    with pytest.raises(AssertionError):
        _destination_base_dir(node, job)


@pytest.mark.django_db
def test_destination_base_dir_sanitizes_username(tmp_path: Path):
    """Usernames with special chars should be sanitized in the folder name."""
    user = UserFactory.create(username="user/with:special")
    destination = DicomFolderFactory.create(path=str(tmp_path))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
    )

    result = _destination_base_dir(destination, job)

    # Should not contain path separators
    folder_name = result.name
    assert "/" not in folder_name
    assert "\\" not in folder_name
    assert result.is_dir()


@pytest.mark.django_db
def test_process_output_path_includes_job_folder(mocker: MockerFixture, tmp_path: Path):
    """End-to-end: process() output path should include job-identifying folder."""
    MassTransferSettings.objects.create()

    user = UserFactory.create(username="researcher")
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create(path=str(tmp_path / "output"))
    job = MassTransferJob.objects.create(
        owner=user,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        partition_granularity=MassTransferJob.PartitionGranularity.DAILY,
        pseudonymize=False,
        pseudonym_salt="",
    )
    job.filters_json = [{"modality": "CT"}]
    job.save(update_fields=["filters_json"])

    now = timezone.now()
    task = MassTransferTask.objects.create(
        job=job,
        source=source,
        destination=destination,
        patient_id="",
        study_uid="",
        partition_start=now,
        partition_end=now + timedelta(hours=23, minutes=59, seconds=59),
        partition_key="20240101",
    )

    series = [_make_discovered(patient_id="PAT1", series_uid="1.2.3.4.5")]

    processor = MassTransferTaskProcessor(task)
    mocker.patch.object(processor, "_discover_series", return_value=series)
    mocker.patch("adit.mass_transfer.processors.DicomOperator")

    export_paths: list[Path] = []

    def fake_export(op, s, path, subject_id, pseudonymizer):
        export_paths.append(path)
        return (1, "", "")

    mocker.patch.object(processor, "_export_series", side_effect=fake_export)

    result = processor.process()

    assert result["status"] == MassTransferTask.Status.SUCCESS
    assert len(export_paths) == 1

    # The path should contain the job-identifying folder
    expected_prefix = f"adit_mass_transfer_{job.pk}_{job.created.strftime('%Y%m%d')}_researcher"
    assert expected_prefix in str(export_paths[0])
