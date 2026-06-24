import asyncio
import errno
import threading
from pathlib import Path
from time import sleep

import pytest
from django.conf import settings
from pydicom import Dataset
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,  # type: ignore
    StudyRootQueryRetrieveInformationModelFind,  # type: ignore
)
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from adit.core.errors import DicomError
from adit.core.factories import DicomWebServerFactory
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import FileTransmitServer
from adit.core.utils.testing_helpers import (
    DicomTestHelper,
    create_association_mock,
    create_dicom_operator,
)


def _make_result(**kwargs) -> ResultDataset:
    ds = Dataset()
    for key, value in kwargs.items():
        setattr(ds, key, value)
    return ResultDataset(ds)


def create_dicomweb_operator() -> DicomOperator:
    """A DicomOperator whose server only supports DICOMweb (QIDO/WADO/STOW)."""
    server = DicomWebServerFactory.create()
    return DicomOperator(server)


@pytest.mark.django_db
def test_find_patients(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientName": "Foo^Bar", "PatientID": "1001"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(dicom_operator.find_patients(QueryDataset.create(PatientName="Foo^Bar")))

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert (
        association_mock.send_c_find.call_args.args[1]
        == PatientRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_find_studies_with_patient_root(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientID": "12345"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(dicom_operator.find_studies(QueryDataset.create(PatientID="12345")))

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert (
        association_mock.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_find_studies_with_study_root(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientName": "Foo^Bar"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(dicom_operator.find_studies(QueryDataset.create(PatientName="Foo^Bar")))

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientName == responses[0]["PatientName"]
    assert (
        association_mock.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_find_series(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientID": "12345", "StudyInstanceUID": "1.123"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(
        dicom_operator.find_series(QueryDataset.create(PatientID="12345", StudyInstanceUID="1.123"))
    )

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert (
        association_mock.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_download_series_with_c_get(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    association_mock.send_c_get.return_value = DicomTestHelper.create_successful_c_get_response()
    path = Path(settings.BASE_PATH) / "samples" / "dicoms"
    ds = read_dataset(next(path.rglob("*.dcm")))
    received_ds = []
    dicom_operator = create_dicom_operator()

    # Act
    dicom_operator.fetch_series(
        ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: received_ds.append(ds)
    )

    # Assert
    association_mock.send_c_get.assert_called_once()

    # TODO: This test could be improved, unfortunately the callback of  fetch_series will never get
    # called when we just mock send_c_get. And so we can't assert anything on received_ds.


@pytest.mark.django_db
def test_download_series_with_c_move(settings: SettingsWrapper, mocker: MockerFixture):
    # Arrange
    settings.FILE_TRANSMIT_HOST = "127.0.0.1"
    settings.FILE_TRANSMIT_PORT = 17999
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    association_mock.send_c_move.return_value = DicomTestHelper.create_successful_c_move_response()
    dicom_operator = create_dicom_operator()
    dicom_operator.server.study_root_get_support = False
    dicom_operator.server.patient_root_get_support = False
    path = Path(settings.BASE_PATH) / "samples" / "dicoms"
    file_path = next(path.rglob("*.dcm"))
    ds = read_dataset(file_path)
    responses = [{"SOPInstanceUID": ds.SOPInstanceUID}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )

    subscribed_topic = ""

    def start_transmit_server():
        transmit_server = FileTransmitServer("127.0.0.1", 17999)

        async def on_subscribe(topic: str):
            nonlocal subscribed_topic
            subscribed_topic = topic
            await transmit_server.publish_file(
                topic, file_path, {"SOPInstanceUID": ds.SOPInstanceUID}
            )

        transmit_server.set_subscribe_handler(on_subscribe)
        asyncio.run(transmit_server.start(), debug=True)

    threading.Thread(target=start_transmit_server, daemon=True).start()

    # Make sure transmit server is started
    sleep(0.5)

    received_ds = []

    # Act
    dicom_operator.fetch_series(
        ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: received_ds.append(ds)
    )

    # Assert
    assert subscribed_topic == (f"{dicom_operator.server.ae_title}\\{ds.StudyInstanceUID}")
    association_mock.send_c_move.assert_called_once()
    assert received_ds[0] == ds


# ---------------------------------------------------------------------------
# DICOMweb (QIDO) find paths and programmatic filtering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_patients_with_qido_and_dedup(mocker: MockerFixture):
    """DICOMweb server: study-level QIDO results are deduplicated to unique patients."""
    operator = create_dicomweb_operator()
    results = [
        _make_result(PatientID="1001", PatientName="Foo^Bar", PatientBirthDate="20000101"),
        _make_result(PatientID="1001", PatientName="Foo^Bar", PatientBirthDate="20000101"),
        _make_result(PatientID="1002", PatientName="Baz^Qux", PatientBirthDate="19900202"),
    ]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    patients = list(operator.find_patients(QueryDataset.create(PatientName="*")))

    qido_mock.assert_called_once()
    # Query retrieve level is forced to STUDY for QIDO patient emulation
    assert qido_mock.call_args.args[0].QueryRetrieveLevel == "STUDY"
    assert [p.PatientID for p in patients] == ["1001", "1002"]


@pytest.mark.django_db
def test_find_patients_filters_by_birth_date_name_and_sex(mocker: MockerFixture):
    operator = create_dicom_operator()
    results = [
        _make_result(PatientID="1", PatientName="Foo^Bar", PatientBirthDate="20000101", PatientSex="M"),  # noqa: E501
        _make_result(PatientID="2", PatientName="Foo^Baz", PatientBirthDate="20000101", PatientSex="M"),  # noqa: E501
        _make_result(PatientID="3", PatientName="Foo^Bar", PatientBirthDate="19991231", PatientSex="M"),  # noqa: E501
        _make_result(PatientID="4", PatientName="Foo^Bar", PatientBirthDate="20000101", PatientSex="F"),  # noqa: E501
    ]
    mocker.patch.object(
        operator.dimse_connector, "send_c_find", return_value=iter(results)
    )

    # PatientSex is not a `create()` kwarg, so build the query dataset directly.
    query_ds = Dataset()
    query_ds.PatientName = "Foo^Bar"
    query_ds.PatientBirthDate = "20000101"
    query_ds.PatientSex = "M"
    query = QueryDataset(query_ds)
    patients = list(operator.find_patients(query))

    # Only patient 1 matches all three filters
    assert [p.PatientID for p in patients] == ["1"]


@pytest.mark.django_db
def test_find_patients_raises_when_no_method_supported(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.patient_root_find_support = False
    operator.server.study_root_find_support = False
    operator.server.dicomweb_qido_support = False

    with pytest.raises(DicomError, match="No supported method to find patients"):
        list(operator.find_patients(QueryDataset.create(PatientID="1")))


@pytest.mark.django_db
def test_find_studies_with_qido_filters_description_and_modalities(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    results = [
        _make_result(
            PatientID="1",
            StudyInstanceUID="1.1",
            StudyDescription="Brain CT",
            ModalitiesInStudy=["CT"],
        ),
        _make_result(
            PatientID="1",
            StudyInstanceUID="1.2",
            StudyDescription="Chest XR",
            ModalitiesInStudy=["XR"],
        ),
    ]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    query = QueryDataset.create(StudyDescription="Brain*", ModalitiesInStudy="CT")
    studies = list(operator.find_studies(query))

    qido_mock.assert_called_once()
    assert [s.StudyInstanceUID for s in studies] == ["1.1"]


@pytest.mark.django_db
def test_find_studies_raises_when_no_method_supported(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.patient_root_find_support = False
    operator.server.study_root_find_support = False
    operator.server.dicomweb_qido_support = False

    with pytest.raises(DicomError, match="No supported method to find studies"):
        list(operator.find_studies(QueryDataset.create(PatientID="1")))


@pytest.mark.django_db
def test_find_series_requires_valid_study_uid():
    operator = create_dicom_operator()

    with pytest.raises(DicomError, match="valid StudyInstanceUID is required"):
        list(operator.find_series(QueryDataset.create(PatientID="1")))

    with pytest.raises(DicomError, match="valid StudyInstanceUID is required"):
        list(operator.find_series(QueryDataset.create(PatientID="1", StudyInstanceUID="1.*")))


@pytest.mark.django_db
def test_find_series_patient_root_requires_patient_id(mocker: MockerFixture):
    """With only patient root support, querying series without a PatientID raises."""
    operator = create_dicom_operator()
    operator.server.study_root_find_support = False
    operator.server.patient_root_find_support = True

    with pytest.raises(DicomError, match="PatientID is required for querying series"):
        list(operator.find_series(QueryDataset.create(StudyInstanceUID="1.123")))


@pytest.mark.django_db
def test_find_series_filters_number_modality_and_description(mocker: MockerFixture):
    operator = create_dicom_operator()
    results = [
        _make_result(
            SeriesInstanceUID="s1", SeriesNumber=1, Modality="CT", SeriesDescription="Axial"
        ),
        _make_result(
            SeriesInstanceUID="s2", SeriesNumber=2, Modality="CT", SeriesDescription="Axial"
        ),
        _make_result(
            SeriesInstanceUID="s3", SeriesNumber=1, Modality="MR", SeriesDescription="Axial"
        ),
        _make_result(
            SeriesInstanceUID="s4", SeriesNumber=1, Modality="CT", SeriesDescription="Sagittal"
        ),
    ]
    mocker.patch.object(
        operator.dimse_connector, "send_c_find", return_value=iter(results)
    )

    query = QueryDataset.create(
        PatientID="1",
        StudyInstanceUID="1.123",
        SeriesNumber=1,
        Modality="CT",
        SeriesDescription="Axial",
    )
    series = list(operator.find_series(query))

    assert [s.SeriesInstanceUID for s in series] == ["s1"]


@pytest.mark.django_db
def test_find_series_uses_qido_when_only_dicomweb(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    results = [_make_result(SeriesInstanceUID="s1", PatientID="1", StudyInstanceUID="1.123")]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    series = list(
        operator.find_series(QueryDataset.create(PatientID="1", StudyInstanceUID="1.123"))
    )

    qido_mock.assert_called_once()
    assert series[0].SeriesInstanceUID == "s1"


@pytest.mark.django_db
def test_find_images_requires_valid_study_and_series_uid():
    operator = create_dicom_operator()

    with pytest.raises(DicomError, match="valid StudyInstanceUID is required"):
        list(operator.find_images(QueryDataset.create(PatientID="1", SeriesInstanceUID="s1")))

    with pytest.raises(DicomError, match="valid SeriesInstanceUID is required"):
        list(operator.find_images(QueryDataset.create(PatientID="1", StudyInstanceUID="1.123")))


@pytest.mark.django_db
def test_find_images_patient_root_requires_patient_id(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.study_root_find_support = False
    operator.server.patient_root_find_support = True

    with pytest.raises(DicomError, match="PatientID is required for querying images"):
        list(
            operator.find_images(
                QueryDataset.create(StudyInstanceUID="1.123", SeriesInstanceUID="s1")
            )
        )


@pytest.mark.django_db
def test_find_images_with_c_find(mocker: MockerFixture):
    operator = create_dicom_operator()
    results = [_make_result(SOPInstanceUID="i1"), _make_result(SOPInstanceUID="i2")]
    find_mock = mocker.patch.object(
        operator.dimse_connector, "send_c_find", return_value=iter(results)
    )

    images = list(
        operator.find_images(
            QueryDataset.create(PatientID="1", StudyInstanceUID="1.123", SeriesInstanceUID="s1")
        )
    )

    find_mock.assert_called_once()
    assert [i.SOPInstanceUID for i in images] == ["i1", "i2"]


@pytest.mark.django_db
def test_find_images_with_qido(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    results = [_make_result(SOPInstanceUID="i1")]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    images = list(
        operator.find_images(
            QueryDataset.create(PatientID="1", StudyInstanceUID="1.123", SeriesInstanceUID="s1")
        )
    )

    qido_mock.assert_called_once()
    assert images[0].SOPInstanceUID == "i1"


@pytest.mark.django_db
def test_find_images_raises_when_no_method_supported(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.patient_root_find_support = False
    operator.server.study_root_find_support = False
    operator.server.dicomweb_qido_support = False

    with pytest.raises(DicomError, match="No supported method to find images"):
        list(
            operator.find_images(
                QueryDataset.create(PatientID="1", StudyInstanceUID="1.123", SeriesInstanceUID="s1")
            )
        )


# ---------------------------------------------------------------------------
# fetch_* dispatch (WADO preferred) and "no supported method" errors
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_study_prefers_wado(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    image = Dataset()
    image.SOPInstanceUID = "i1"
    wado_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_wado_rs", return_value=iter([image])
    )

    received: list[Dataset] = []
    operator.fetch_study("1", "1.123", received.append)

    wado_mock.assert_called_once()
    assert received[0].SOPInstanceUID == "i1"


@pytest.mark.django_db
def test_fetch_study_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    for attr in (
        "dicomweb_wado_support",
        "patient_root_get_support",
        "study_root_get_support",
        "patient_root_move_support",
        "study_root_move_support",
    ):
        setattr(operator.server, attr, False)

    with pytest.raises(DicomError, match="No supported method to fetch a study"):
        operator.fetch_study("1", "1.123", lambda ds: None)


@pytest.mark.django_db
def test_fetch_series_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    for attr in (
        "dicomweb_wado_support",
        "patient_root_get_support",
        "study_root_get_support",
        "patient_root_move_support",
        "study_root_move_support",
    ):
        setattr(operator.server, attr, False)

    with pytest.raises(DicomError, match="No supported method to fetch a series"):
        operator.fetch_series("1", "1.123", "s1", lambda ds: None)


@pytest.mark.django_db
def test_fetch_image_prefers_wado(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    image = Dataset()
    image.SOPInstanceUID = "i1"
    wado_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_wado_rs", return_value=iter([image])
    )

    received: list[Dataset] = []
    operator.fetch_image("1", "1.123", "s1", "i1", received.append)

    wado_mock.assert_called_once()
    assert received[0].SOPInstanceUID == "i1"


@pytest.mark.django_db
def test_fetch_image_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    for attr in (
        "dicomweb_wado_support",
        "patient_root_get_support",
        "study_root_get_support",
        "patient_root_move_support",
        "study_root_move_support",
    ):
        setattr(operator.server, attr, False)

    with pytest.raises(DicomError, match="No supported method to fetch an image"):
        operator.fetch_image("1", "1.123", "s1", "i1", lambda ds: None)


# ---------------------------------------------------------------------------
# upload_images
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_images_uses_c_store(mocker: MockerFixture):
    operator = create_dicom_operator()
    store_mock = mocker.patch.object(operator.dimse_connector, "send_c_store")
    datasets = [Dataset()]

    operator.upload_images(datasets)

    store_mock.assert_called_once_with(datasets)


@pytest.mark.django_db
def test_upload_images_uses_stow_when_only_dicomweb(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    stow_mock = mocker.patch.object(operator.dicom_web_connector, "send_stow_rs")
    datasets = [Dataset()]

    operator.upload_images(datasets)

    stow_mock.assert_called_once_with(datasets)


@pytest.mark.django_db
def test_upload_images_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.store_scp_support = False
    operator.server.dicomweb_stow_support = False

    with pytest.raises(DicomError, match="No supported method to upload images"):
        operator.upload_images([Dataset()])


# ---------------------------------------------------------------------------
# move_study / move_series
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_move_study_sends_c_move(mocker: MockerFixture):
    operator = create_dicom_operator()
    move_mock = mocker.patch.object(operator.dimse_connector, "send_c_move")

    operator.move_study("1", "1.123", "DEST_AE")

    move_mock.assert_called_once()
    query, dest = move_mock.call_args.args
    assert query.QueryRetrieveLevel == "STUDY"
    assert query.StudyInstanceUID == "1.123"
    assert dest == "DEST_AE"


@pytest.mark.django_db
def test_move_study_raises_when_unsupported():
    operator = create_dicom_operator()
    operator.server.patient_root_move_support = False
    operator.server.study_root_move_support = False

    with pytest.raises(DicomError, match="does not support moving a study"):
        operator.move_study("1", "1.123", "DEST_AE")


@pytest.mark.django_db
def test_move_series_sends_c_move(mocker: MockerFixture):
    operator = create_dicom_operator()
    move_mock = mocker.patch.object(operator.dimse_connector, "send_c_move")

    operator.move_series("1", "1.123", "s1", "DEST_AE")

    move_mock.assert_called_once()
    query, dest = move_mock.call_args.args
    assert query.QueryRetrieveLevel == "SERIES"
    assert query.SeriesInstanceUID == "s1"
    assert dest == "DEST_AE"


@pytest.mark.django_db
def test_move_series_raises_when_unsupported():
    operator = create_dicom_operator()
    operator.server.patient_root_move_support = False
    operator.server.study_root_move_support = False

    with pytest.raises(DicomError, match="does not support moving a series"):
        operator.move_series("1", "1.123", "s1", "DEST_AE")


# ---------------------------------------------------------------------------
# _fetch_images_with_c_get store handler (success + error abort path)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_with_c_get_store_handler_success(mocker: MockerFixture):
    """The store handler invokes the callback and returns the success status code."""
    operator = create_dicom_operator()
    captured: dict = {}

    def fake_send_c_get(query, store_handler, store_errors, *args, **kwargs):
        # Simulate pynetdicom firing the store handler with one event
        event = mocker.MagicMock()
        ds = Dataset()
        ds.SOPInstanceUID = "i1"
        event.dataset = ds
        event.file_meta = Dataset()
        captured["rc"] = store_handler(event, store_errors)

    mocker.patch.object(operator.dimse_connector, "send_c_get", side_effect=fake_send_c_get)

    received: list[Dataset] = []
    operator.fetch_series("1", "1.123", "s1", received.append)

    assert captured["rc"] == 0x0000
    assert received[0].SOPInstanceUID == "i1"


@pytest.mark.django_db
def test_fetch_with_c_get_store_handler_error_aborts_and_raises(mocker: MockerFixture):
    """A failing callback records the error, aborts the association, returns 0xA702,
    and the collected error is re-raised after send_c_get returns."""
    operator = create_dicom_operator()
    abort_mock = mocker.patch.object(operator.dimse_connector, "abort_connection")

    def bad_callback(ds: Dataset) -> None:
        raise ValueError("boom")

    def fake_send_c_get(query, store_handler, store_errors, *args, **kwargs):
        event = mocker.MagicMock()
        ds = Dataset()
        ds.SOPInstanceUID = "i1"
        event.dataset = ds
        event.file_meta = Dataset()
        rc = store_handler(event, store_errors)
        assert rc == 0xA702
        event.assoc.abort.assert_called_once()

    mocker.patch.object(operator.dimse_connector, "send_c_get", side_effect=fake_send_c_get)

    with pytest.raises(DicomError, match="Failed to handle image"):
        operator.fetch_series("1", "1.123", "s1", bad_callback)

    abort_mock.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_fetched_image error mapping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_handle_fetched_image_out_of_space(mocker: MockerFixture):
    operator = create_dicom_operator()
    ds = Dataset()
    ds.SOPInstanceUID = "i1"

    def callback(_ds: Dataset) -> None:
        err = OSError("no space")
        err.errno = errno.ENOSPC
        err.filename = "/tmp/out.dcm"
        raise err

    with pytest.raises(DicomError, match="Out of disk space"):
        operator._handle_fetched_image(ds, callback)


@pytest.mark.django_db
def test_handle_fetched_image_generic_error(mocker: MockerFixture):
    operator = create_dicom_operator()
    ds = Dataset()
    ds.SOPInstanceUID = "i1"

    def callback(_ds: Dataset) -> None:
        raise RuntimeError("unexpected")

    with pytest.raises(DicomError, match="Failed to handle image 'i1'"):
        operator._handle_fetched_image(ds, callback)


# ---------------------------------------------------------------------------
# get_logs / close / abort
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_logs_aggregates_connector_logs(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.dimse_connector.logs = [{"level": "Warning", "title": "a", "message": "m1"}]
    operator.dicom_web_connector.logs = [{"level": "Warning", "title": "b", "message": "m2"}]
    operator.logs = [{"level": "Warning", "title": "c", "message": "m3"}]

    logs = operator.get_logs()

    assert [log["message"] for log in logs] == ["m1", "m2", "m3"]


@pytest.mark.django_db
def test_close_releases_open_association(mocker: MockerFixture):
    operator = create_dicom_operator()
    close_mock = mocker.patch.object(operator.dimse_connector, "close_connection")
    operator.dimse_connector.assoc = create_association_mock()

    operator.close()

    close_mock.assert_called_once()


@pytest.mark.django_db
def test_close_swallows_errors(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.dimse_connector.assoc = create_association_mock()
    mocker.patch.object(
        operator.dimse_connector, "close_connection", side_effect=RuntimeError("fail")
    )

    # Should not raise
    operator.close()


@pytest.mark.django_db
def test_abort_aborts_both_connectors(mocker: MockerFixture):
    operator = create_dicom_operator()
    dimse_abort = mocker.patch.object(operator.dimse_connector, "abort_connection")
    web_abort = mocker.patch.object(operator.dicom_web_connector, "abort")

    operator.abort()

    dimse_abort.assert_called_once()
    web_abort.assert_called_once()
