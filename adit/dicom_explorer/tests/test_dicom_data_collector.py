import pytest
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.core.factories import DicomServerFactory
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.dicom_explorer.utils.dicom_data_collector import DicomDataCollector


def _patient(patient_id: str, patient_name: str) -> ResultDataset:
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientName = patient_name
    return ResultDataset(ds)


def _series(series_uid: str, series_number) -> ResultDataset:
    ds = Dataset()
    ds.SeriesInstanceUID = series_uid
    ds.SeriesNumber = series_number
    ds.Modality = "CT"
    return ResultDataset(ds)


@pytest.mark.django_db
def test_collect_patients_sorted_by_name(mocker: MockerFixture):
    # The operator is mocked at the boundary; no live PACS is contacted.
    server = DicomServerFactory.create()
    operator_mock = mocker.patch(
        "adit.dicom_explorer.utils.dicom_data_collector.DicomOperator"
    ).return_value
    operator_mock.find_patients.return_value = iter(
        [_patient("2", "Zulu^Zoe"), _patient("1", "Alpha^Anna")]
    )

    collector = DicomDataCollector(server)
    patients = collector.collect_patients(QueryDataset.create(PatientID=""), limit_results=10)

    assert [str(p.PatientName) for p in patients] == ["Alpha^Anna", "Zulu^Zoe"]
    operator_mock.find_patients.assert_called_once()
    # The result limit must be forwarded to the operator.
    assert operator_mock.find_patients.call_args.kwargs["limit_results"] == 10


@pytest.mark.django_db
def test_collect_series_sorted_by_series_number(mocker: MockerFixture):
    server = DicomServerFactory.create()
    operator_mock = mocker.patch(
        "adit.dicom_explorer.utils.dicom_data_collector.DicomOperator"
    ).return_value
    # A series with SeriesNumber None must sort last (treated as +inf).
    operator_mock.find_series.return_value = iter(
        [_series("1.2", 3), _series("1.3", None), _series("1.4", 1)]
    )

    collector = DicomDataCollector(server)
    series_list = collector.collect_series(QueryDataset.create(StudyInstanceUID="1.2.3"))

    assert [s.SeriesInstanceUID for s in series_list] == ["1.4", "1.2", "1.3"]


@pytest.mark.django_db
def test_collect_series_requires_study_uid(mocker: MockerFixture):
    server = DicomServerFactory.create()
    mocker.patch("adit.dicom_explorer.utils.dicom_data_collector.DicomOperator")

    collector = DicomDataCollector(server)
    with pytest.raises(AssertionError, match="Missing Study Instance UID"):
        collector.collect_series(QueryDataset.create(PatientID="1001"))
