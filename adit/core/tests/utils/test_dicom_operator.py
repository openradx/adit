import asyncio
import filecmp
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from unittest.mock import patch

from django.conf import settings
from pydicom import Dataset
from pynetdicom.association import Association
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,  # type: ignore
    StudyRootQueryRetrieveInformationModelFind,  # type: ignore
)
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import FileTransmitServer

from .conftest import DicomTestHelper


@patch("adit.core.utils.dimse_connector.AE.associate")
def test_find_patients(
    associate,
    association: Association,
    dicom_operator: DicomOperator,
    dicom_test_helper: DicomTestHelper,
):
    # Arrange
    associate.return_value = association
    responses = [{"PatientName": "Foo^Bar", "PatientID": "1001"}]
    association.send_c_find.return_value = dicom_test_helper.create_successful_c_find_responses(
        responses
    )

    # Act
    patients = list(dicom_operator.find_patients(QueryDataset.create(PatientName="Foo^Bar")))

    # Assert
    association.send_c_find.assert_called_once()
    assert isinstance(association.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert association.send_c_find.call_args.args[1] == PatientRootQueryRetrieveInformationModelFind


@patch("adit.core.utils.dimse_connector.AE.associate")
def test_find_studies_with_patient_root(
    associate,
    association: Association,
    dicom_operator: DicomOperator,
    dicom_test_helper: DicomTestHelper,
):
    # Arrange
    associate.return_value = association
    responses = [{"PatientID": "12345"}]
    association.send_c_find.return_value = dicom_test_helper.create_successful_c_find_responses(
        responses
    )

    # Act
    patients = list(dicom_operator.find_studies(QueryDataset.create(PatientID="12345")))

    # Assert
    association.send_c_find.assert_called_once()
    assert isinstance(association.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert association.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind


@patch("adit.core.utils.dimse_connector.AE.associate")
def test_find_studies_with_study_root(
    associate,
    association: Association,
    dicom_operator: DicomOperator,
    dicom_test_helper: DicomTestHelper,
):
    # Arrange
    associate.return_value = association
    responses = [{"PatientName": "Foo^Bar"}]
    association.send_c_find.return_value = dicom_test_helper.create_successful_c_find_responses(
        responses
    )

    # Act
    patients = list(dicom_operator.find_studies(QueryDataset.create(PatientName="Foo^Bar")))

    # Assert
    association.send_c_find.assert_called_once()
    assert isinstance(association.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientName == responses[0]["PatientName"]
    assert association.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind


@patch("adit.core.utils.dimse_connector.AE.associate")
def test_find_series(
    associate,
    association: Association,
    dicom_operator: DicomOperator,
    dicom_test_helper: DicomTestHelper,
):
    # Arrange
    associate.return_value = association
    responses = [{"PatientID": "12345", "StudyInstanceUID": "1.123"}]
    association.send_c_find.return_value = dicom_test_helper.create_successful_c_find_responses(
        responses
    )

    # Act
    patients = list(
        dicom_operator.find_series(QueryDataset.create(PatientID="12345", StudyInstanceUID="1.123"))
    )

    # Assert
    association.send_c_find.assert_called_once()
    assert isinstance(association.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert association.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind


def test_download_series_with_c_get(
    mocker: MockerFixture,
    association: Association,
    dicom_operator: DicomOperator,
    dicom_test_helper: DicomTestHelper,
):
    # Arrange
    mocker.patch("adit.core.utils.dimse_connector.AE.associate", return_value=association)
    association.send_c_get.return_value = dicom_test_helper.create_successful_c_get_response()
    path = Path(settings.BASE_DIR) / "samples" / "dicoms"
    ds = read_dataset(next(path.rglob("*.dcm")))
    with TemporaryDirectory() as tmp_dir:
        # Act
        dicom_operator.download_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, Path(tmp_dir)
        )

        # Assert
        association.send_c_get.assert_called_once()


def test_download_series_with_c_move(
    settings: SettingsWrapper,
    mocker: MockerFixture,
    association: Association,
    dicom_operator: DicomOperator,
    dicom_test_helper: DicomTestHelper,
):
    # Arrange
    settings.FILE_TRANSMIT_HOST = "127.0.0.1"
    settings.FILE_TRANSMIT_PORT = 17999
    mocker.patch("adit.core.utils.dimse_connector.AE.associate", return_value=association)
    association.send_c_move.return_value = dicom_test_helper.create_successful_c_move_response()
    dicom_operator.server.study_root_get_support = False
    dicom_operator.server.patient_root_get_support = False
    path = Path(settings.BASE_DIR) / "samples" / "dicoms"
    file_path = next(path.rglob("*.dcm"))
    ds = read_dataset(file_path)
    responses = [{"SOPInstanceUID": ds.SOPInstanceUID}]
    association.send_c_find.return_value = dicom_test_helper.create_successful_c_find_responses(
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

    with TemporaryDirectory() as tmp_dir:
        # Act
        dicom_operator.download_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, Path(tmp_dir)
        )

        # Assert
        assert subscribed_topic == (
            f"{dicom_operator.server.ae_title}\\{ds.StudyInstanceUID}\\{ds.SeriesInstanceUID}"
        )
        association.send_c_move.assert_called_once()
        assert filecmp.cmp(next(Path(tmp_dir).iterdir()), file_path)
