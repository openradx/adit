import asyncio
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

from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import FileTransmitServer
from adit.core.utils.testing_helpers import (
    DicomTestHelper,
    create_association_mock,
    create_dicom_operator,
)


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
    path = Path(settings.BASE_DIR) / "samples" / "dicoms"
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
    path = Path(settings.BASE_DIR) / "samples" / "dicoms"
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
    assert subscribed_topic == (
        f"{dicom_operator.server.ae_title}\\{ds.StudyInstanceUID}\\{ds.SeriesInstanceUID}"
    )
    association_mock.send_c_move.assert_called_once()
    assert received_ds[0] == ds
