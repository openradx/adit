from unittest.mock import patch, create_autospec, ANY
import datetime
import pytest
import factory
import time_machine
from django.db import models, connection
from django.db.utils import ProgrammingError
from adit.accounts.factories import UserFactory
from ...models import TransferJob, TransferTask
from ...factories import (
    DicomServerFactory,
    DicomFolderFactory,
    TransferJobFactory,
    TransferTaskFactory,
)
from ...utils.dicom_connector import DicomConnector
from ...utils.transfer_utils import execute_transfer


class MyTransferJob(TransferJob):
    class Meta:
        app_label = "adit.core"


class MyTransferTask(TransferTask):
    class Meta:
        app_label = "adit.core"

    job = models.ForeignKey(
        MyTransferJob, on_delete=models.CASCADE, related_name="tasks"
    )


class MyTransferJobFactory(TransferJobFactory):
    class Meta:
        model = MyTransferJob


class MyTransferTaskFactory(TransferTaskFactory):
    class Meta:
        model = MyTransferTask

    job = factory.SubFactory(MyTransferJobFactory)


@pytest.fixture(scope="session")
def setup_test_models(django_db_setup, django_db_blocker):
    # Solution adapted from https://stackoverflow.com/q/4281670/166229
    with django_db_blocker.unblock():
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(MyTransferJob)
                schema_editor.create_model(MyTransferTask)
        except ProgrammingError:
            pass

        yield

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(MyTransferJob)
            schema_editor.delete_model(MyTransferTask)

        connection.close()


@pytest.fixture
def create_resources():
    def _create_resources(transfer_task):
        patient = {"PatientID": transfer_task.patient_id}
        study = {
            "PatientID": transfer_task.patient_id,
            "StudyInstanceUID": transfer_task.study_uid,
            "StudyDate": datetime.date(2019, 9, 23),
            "StudyTime": datetime.time(8, 0),
            "ModalitiesInStudy": ["CT", "SR"],
        }

        return patient, study

    return _create_resources


@pytest.mark.django_db
@patch("adit.core.utils.transfer_utils._create_dest_connector", autospec=True)
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
def test_transfer_to_server_succeeds(
    mock_create_source_connector,
    mock_create_dest_connector,
    setup_test_models,
    create_resources,
):
    # Arrange
    job = MyTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        archive_password="",
    )
    task = MyTransferTaskFactory(
        status=TransferTask.Status.PENDING, series_uids=[], pseudonym="", job=job
    )

    patient, study = create_resources(task)

    mock_source_connector = create_autospec(DicomConnector)
    mock_source_connector.find_patients.return_value = [patient]
    mock_source_connector.find_studies.return_value = [study]
    mock_create_source_connector.return_value = mock_source_connector
    mock_dest_connector = create_autospec(DicomConnector)
    mock_create_dest_connector.return_value = mock_dest_connector

    # Act
    status = execute_transfer(task)

    # Assert
    mock_source_connector.download_study.assert_called_with(
        task.patient_id, task.study_uid, ANY, modifier_callback=ANY
    )

    upload_path = mock_dest_connector.upload_folder.call_args[0][0]
    assert upload_path.match(f"*/{study['PatientID']}")

    assert status == task.status
    assert status == MyTransferTask.Status.SUCCESS


@pytest.mark.django_db
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_succeeds(
    mock_create_source_connector, setup_test_models, create_resources
):
    # Arrange
    user = UserFactory(username="kai")
    job = MyTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="",
        owner=user,
    )
    task = MyTransferTaskFactory(
        status=TransferTask.Status.PENDING,
        patient_id="1001",
        series_uids=[],
        pseudonym="",
    )
    task.job = job

    patient, study = create_resources(task)

    mock_source_connector = create_autospec(DicomConnector)
    mock_source_connector.find_patients.return_value = [patient]
    mock_source_connector.find_studies.return_value = [study]
    mock_create_source_connector.return_value = mock_source_connector

    # Act
    with patch("adit.core.utils.transfer_utils.Path.mkdir", autospec=True):
        status = execute_transfer(task)

    # Assert
    download_path = mock_source_connector.download_study.call_args[0][2]
    assert download_path.match(
        r"adit_adit.core_1_20200101_kai/1001/20190923-080000-CT,SR"
    )

    assert status == task.status
    assert status == MyTransferTask.Status.SUCCESS


@pytest.mark.django_db
@patch("subprocess.Popen")
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
def test_transfer_to_archive_succeeds(
    mock_create_source_connector, mock_Popen, setup_test_models, create_resources
):
    # Arrange
    job = MyTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="mysecret",
    )
    task = MyTransferTaskFactory(
        status=TransferTask.Status.PENDING, series_uids=[], pseudonym=""
    )
    task.job = job

    patient, study = create_resources(task)

    mock_source_connector = create_autospec(DicomConnector)
    mock_source_connector.find_patients.return_value = [patient]
    mock_source_connector.find_studies.return_value = [study]
    mock_create_source_connector.return_value = mock_source_connector

    mock_Popen.return_value.returncode = 0
    mock_Popen.return_value.communicate.return_value = ("", "")

    # Act
    status = execute_transfer(task)

    # Assert
    mock_source_connector.find_patients.assert_called_once()
    assert mock_Popen.call_args[0][0][0] == "7z"
    assert mock_Popen.call_count == 2

    assert status == task.status
    assert status == MyTransferTask.Status.SUCCESS
