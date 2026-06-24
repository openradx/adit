"""Tests for the BatchQueryTaskProcessor query/processing logic.

The DICOM network is mocked at the DicomOperator boundary so no live PACS is
needed: each processor's `operator` attribute is replaced with a mock whose
`find_patients` / `find_studies` / `find_series` return crafted ResultDatasets.
"""

from datetime import date

import pytest
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.batch_query.factories import BatchQueryJobFactory, BatchQueryTaskFactory
from adit.batch_query.models import BatchQueryResult, BatchQueryTask
from adit.batch_query.processors import BatchQueryTaskProcessor
from adit.core.errors import DicomError
from adit.core.factories import DicomServerFactory
from adit.core.utils.dicom_dataset import ResultDataset


def _patient(patient_id="1001", name="Foo^Bar", birth_date="20000101") -> ResultDataset:
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientName = name
    ds.PatientBirthDate = birth_date
    return ResultDataset(ds)


def _study(
    *,
    patient_id="1001",
    name="Foo^Bar",
    birth_date="20000101",
    study_uid="1.2.3",
    accession_number="ACC1",
    study_date="20240101",
    study_time="120000",
    description="Brain CT",
    modalities=None,
    image_count=10,
) -> ResultDataset:
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientName = name
    ds.PatientBirthDate = birth_date
    ds.StudyInstanceUID = study_uid
    ds.AccessionNumber = accession_number
    ds.StudyDate = study_date
    ds.StudyTime = study_time
    ds.StudyDescription = description
    ds.ModalitiesInStudy = modalities if modalities is not None else ["CT"]
    ds.NumberOfStudyRelatedInstances = image_count
    return ResultDataset(ds)


def _series(
    *, series_uid="1.2.3.4", description="Axial", number=1, modality="CT"
) -> ResultDataset:
    ds = Dataset()
    ds.SeriesInstanceUID = series_uid
    ds.SeriesDescription = description
    ds.SeriesNumber = number
    ds.Modality = modality
    return ResultDataset(ds)


def _make_processor(
    mocker: MockerFixture,
    *,
    patient_id="1001",
    patient_name="",
    patient_birth_date=None,
    modalities=None,
    accession_number="",
    study_description="",
    series_description="",
    series_numbers=None,
    study_date_start=None,
    study_date_end=None,
) -> BatchQueryTaskProcessor:
    """Create a DB-backed BatchQueryTask and a processor with a mocked operator."""
    source = DicomServerFactory.create()
    job = BatchQueryJobFactory.create()
    task = BatchQueryTaskFactory.create(
        job=job,
        source=source,
        patient_id=patient_id,
        patient_name=patient_name,
        patient_birth_date=patient_birth_date,
        accession_number=accession_number,
        modalities=modalities if modalities is not None else [],
        study_description=study_description,
        series_description=series_description,
        series_numbers=series_numbers if series_numbers is not None else [],
        study_date_start=study_date_start,
        study_date_end=study_date_end,
    )
    processor = BatchQueryTaskProcessor(task)
    processor.operator = mocker.MagicMock()
    processor.operator.get_logs.return_value = []
    # Each processor instance must not share the class-level logs list
    processor.logs = []
    return processor


# ---------------------------------------------------------------------------
# _find_patients
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_patients_by_patient_id(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="1001")
    processor.operator.find_patients.return_value = iter([_patient(patient_id="1001")])

    patients = processor._find_patients()

    assert len(patients) == 1
    assert patients[0].PatientID == "1001"


@pytest.mark.django_db
def test_find_patients_by_patient_id_no_patient_raises(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="9999")
    processor.operator.find_patients.return_value = iter([])

    with pytest.raises(DicomError, match="No patient found with this PatientID"):
        processor._find_patients()


@pytest.mark.django_db
def test_find_patients_by_patient_id_multiple_raises(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="1001")
    processor.operator.find_patients.return_value = iter(
        [_patient(patient_id="1001"), _patient(patient_id="1001")]
    )

    with pytest.raises(DicomError, match="Multiple patients found"):
        processor._find_patients()


@pytest.mark.django_db
def test_find_patients_patient_name_mismatch_raises(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="1001", patient_name="Other^Name")
    processor.operator.find_patients.return_value = iter(
        [_patient(patient_id="1001", name="Foo^Bar")]
    )

    with pytest.raises(DicomError, match="PatientName doesn't match"):
        processor._find_patients()


@pytest.mark.django_db
def test_find_patients_birth_date_mismatch_raises(mocker: MockerFixture):
    processor = _make_processor(
        mocker, patient_id="1001", patient_birth_date=date(1999, 12, 31)
    )
    found = _patient(patient_id="1001")
    # ResultDataset.PatientBirthDate returns a date object; mismatch with task value
    processor.operator.find_patients.return_value = iter([found])

    with pytest.raises(DicomError, match="PatientBirthDate doesn't match"):
        processor._find_patients()


@pytest.mark.django_db
def test_find_patients_by_name_and_birth_date(mocker: MockerFixture):
    processor = _make_processor(
        mocker,
        patient_id="",
        patient_name="Foo^Bar",
        patient_birth_date=date(2000, 1, 1),
    )
    processor.operator.find_patients.return_value = iter([_patient()])

    patients = processor._find_patients()

    assert len(patients) == 1


@pytest.mark.django_db
def test_find_patients_by_name_and_birth_date_none_found_raises(mocker: MockerFixture):
    processor = _make_processor(
        mocker,
        patient_id="",
        patient_name="Foo^Bar",
        patient_birth_date=date(2000, 1, 1),
    )
    processor.operator.find_patients.return_value = iter([])

    with pytest.raises(DicomError, match="No patient found with this PatientName"):
        processor._find_patients()


@pytest.mark.django_db
def test_find_patients_without_identifiers_raises(mocker: MockerFixture):
    processor = _make_processor(
        mocker, patient_id="", patient_name="", patient_birth_date=None
    )

    with pytest.raises(DicomError, match="PatientID or PatientName and PatientBirthDate"):
        processor._find_patients()


# ---------------------------------------------------------------------------
# _find_studies
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_studies_without_modalities(mocker: MockerFixture):
    processor = _make_processor(mocker)
    s1 = _study(study_uid="1.2.3", study_date="20240102")
    s2 = _study(study_uid="1.2.4", study_date="20240101")
    processor.operator.find_studies.return_value = iter([s1, s2])

    studies = processor._find_studies("1001")

    # Returned sorted by StudyDate ascending
    assert [s.StudyInstanceUID for s in studies] == ["1.2.4", "1.2.3"]
    processor.operator.find_studies.assert_called_once()


@pytest.mark.django_db
def test_find_studies_with_modalities_deduplicates(mocker: MockerFixture):
    processor = _make_processor(mocker, modalities=["CT", "MR"])

    # One query per modality; same study returned for both must be deduplicated
    ct_study = _study(study_uid="1.2.3", modalities=["CT"])
    mr_study = _study(study_uid="1.2.3", modalities=["MR"])
    other = _study(study_uid="1.2.9", modalities=["MR"])
    processor.operator.find_studies.side_effect = [
        iter([ct_study]),
        iter([mr_study, other]),
    ]

    studies = processor._find_studies("1001")

    uids = sorted(s.StudyInstanceUID for s in studies)
    assert uids == ["1.2.3", "1.2.9"]
    # Two queries: one per modality
    assert processor.operator.find_studies.call_count == 2


# ---------------------------------------------------------------------------
# _find_series
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_series_without_series_numbers(mocker: MockerFixture):
    processor = _make_processor(mocker, series_description="Axial")
    processor.operator.find_series.return_value = iter(
        [_series(series_uid="1.2.3.4", number=2), _series(series_uid="1.2.3.5", number=1)]
    )

    series = processor._find_series("1001", "1.2.3")

    # Sorted by SeriesNumber ascending
    assert [s.SeriesInstanceUID for s in series] == ["1.2.3.5", "1.2.3.4"]


@pytest.mark.django_db
def test_find_series_with_series_numbers_deduplicates(mocker: MockerFixture):
    processor = _make_processor(mocker, series_numbers=["1", "2"])

    s1 = _series(series_uid="1.2.3.5", number=1)
    s2 = _series(series_uid="1.2.3.4", number=2)
    # Same series returned twice across number queries -> dedup
    processor.operator.find_series.side_effect = [
        iter([s1]),
        iter([s1, s2]),
    ]

    series = processor._find_series("1001", "1.2.3")

    uids = [s.SeriesInstanceUID for s in series]
    assert uids == ["1.2.3.5", "1.2.3.4"]
    assert processor.operator.find_series.call_count == 2


# ---------------------------------------------------------------------------
# process() — full study and series flows
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_study_query_creates_results(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="1001")
    processor.operator.find_patients.return_value = iter([_patient(patient_id="1001")])
    processor.operator.find_studies.return_value = iter(
        [_study(study_uid="1.2.3"), _study(study_uid="1.2.4")]
    )

    result = processor.process()

    assert result["status"] == BatchQueryTask.Status.SUCCESS
    assert "2 studies found" in result["message"]
    created = BatchQueryResult.objects.filter(query=processor.query_task)
    assert created.count() == 2
    # Study-level results have empty series fields
    first = created.first()
    assert first is not None
    assert first.series_uid == ""


@pytest.mark.django_db
def test_process_single_study_uses_singular_message(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="1001")
    processor.operator.find_patients.return_value = iter([_patient(patient_id="1001")])
    processor.operator.find_studies.return_value = iter([_study(study_uid="1.2.3")])

    result = processor.process()

    assert "1 study found" in result["message"]


@pytest.mark.django_db
def test_process_series_query_creates_series_results(mocker: MockerFixture):
    processor = _make_processor(
        mocker, patient_id="1001", series_description="Axial"
    )
    processor.operator.find_patients.return_value = iter([_patient(patient_id="1001")])
    processor.operator.find_studies.return_value = iter([_study(study_uid="1.2.3")])
    processor.operator.find_series.return_value = iter(
        [_series(series_uid="1.2.3.4", modality="CT")]
    )

    result = processor.process()

    assert result["status"] == BatchQueryTask.Status.SUCCESS
    assert "1 series found" in result["message"]
    created = BatchQueryResult.objects.filter(query=processor.query_task)
    assert created.count() == 1
    series_result = created.first()
    assert series_result is not None
    assert series_result.series_uid == "1.2.3.4"
    assert series_result.modalities == ["CT"]


@pytest.mark.django_db
def test_process_warning_status_from_logs(mocker: MockerFixture):
    processor = _make_processor(mocker, patient_id="1001")
    processor.operator.find_patients.return_value = iter([_patient(patient_id="1001")])
    processor.operator.find_studies.return_value = iter([_study(study_uid="1.2.3")])
    processor.operator.get_logs.return_value = [
        {"level": "Warning", "title": "Something", "message": "a warning"}
    ]

    result = processor.process()

    assert result["status"] == BatchQueryTask.Status.WARNING
    assert "a warning" in result["log"]


@pytest.mark.django_db
def test_query_studies_indistinct_patients_warning(mocker: MockerFixture):
    """When studies for more than one patient are returned a warning is logged."""
    processor = _make_processor(mocker)
    # Two patient ids, both returning studies -> the second triggers the warning
    processor.operator.find_studies.side_effect = [
        iter([_study(patient_id="1001", study_uid="1.2.3")]),
        iter([_study(patient_id="1002", study_uid="1.2.4")]),
    ]

    results = processor._query_studies(["1001", "1002"])

    assert len(results) == 2
    assert any(log["title"] == "Indistinct patients" for log in processor.logs)


@pytest.mark.django_db
def test_query_series_indistinct_patients_warning(mocker: MockerFixture):
    """The series flow also logs an indistinct-patients warning across patients."""
    processor = _make_processor(mocker, series_description="Axial")
    processor.operator.find_studies.side_effect = [
        iter([_study(patient_id="1001", study_uid="1.2.3")]),
        iter([_study(patient_id="1002", study_uid="1.2.4")]),
    ]
    processor.operator.find_series.side_effect = [
        iter([_series(series_uid="1.2.3.4")]),
        iter([_series(series_uid="1.2.4.4")]),
    ]

    results = processor._query_series(["1001", "1002"])

    assert len(results) == 2
    assert any(log["title"] == "Indistinct patients" for log in processor.logs)
