from unittest.mock import patch, create_autospec, ANY
import datetime
import pytest
import factory
import time_machine
from celery import Task as CeleryTask
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
from ...utils.transfer_utils import TransferExecutor


class MyTransferJob(TransferJob):
    class Meta:
        app_label = "adit.core"


class MyTransferTask(TransferTask):
    class Meta:
        app_label = "adit.core"

    job = models.ForeignKey(MyTransferJob, on_delete=models.CASCADE, related_name="tasks")


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
    create_source_connector_mock,
    create_dest_connector_mock,
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

    source_connector_mock = create_autospec(DicomConnector)
    source_connector_mock.find_patients.return_value = [patient]
    source_connector_mock.find_studies.return_value = [study]
    create_source_connector_mock.return_value = source_connector_mock
    dest_connector_mock = create_autospec(DicomConnector)
    create_dest_connector_mock.return_value = dest_connector_mock

    celery_task_mock = create_autospec(CeleryTask)

    # Act
    status = TransferExecutor(task, celery_task_mock).start()

    # Assert
    source_connector_mock.download_study.assert_called_with(
        task.patient_id,
        task.study_uid,
        ANY,
        modifier_callback=ANY,
    )

    upload_path = dest_connector_mock.upload_folder.call_args[0][0]
    assert upload_path.match(f"*/{study['PatientID']}")

    assert status == task.status
    assert status == MyTransferTask.Status.SUCCESS


@pytest.mark.django_db
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_succeeds(
    create_source_connector_mock, setup_test_models, create_resources
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

    source_connector_mock = create_autospec(DicomConnector)
    source_connector_mock.find_patients.return_value = [patient]
    source_connector_mock.find_studies.return_value = [study]
    create_source_connector_mock.return_value = source_connector_mock

    celery_task_mock = create_autospec(CeleryTask)

    # Act
    with patch("adit.core.utils.transfer_utils.os.mkdir", autospec=True):
        status = TransferExecutor(task, celery_task_mock).start()

    # Assert
    download_path = source_connector_mock.download_study.call_args[0][2]
    assert download_path.match(r"adit_adit.core_1_20200101_kai/1001/20190923-080000-CT")

    assert status == task.status
    assert status == MyTransferTask.Status.SUCCESS


@pytest.mark.django_db
@patch("subprocess.Popen")
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
def test_transfer_to_archive_succeeds(
    create_source_connector_mock, Popen_mock, setup_test_models, create_resources
):
    # Arrange
    job = MyTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="mysecret",
    )
    task = MyTransferTaskFactory(status=TransferTask.Status.PENDING, series_uids=[], pseudonym="")
    task.job = job

    patient, study = create_resources(task)

    source_connector_mock = create_autospec(DicomConnector)
    source_connector_mock.find_patients.return_value = [patient]
    source_connector_mock.find_studies.return_value = [study]
    create_source_connector_mock.return_value = source_connector_mock

    Popen_mock.return_value.returncode = 0
    Popen_mock.return_value.communicate.return_value = ("", "")

    celery_task_mock = create_autospec(CeleryTask)

    # Act
    status = TransferExecutor(task, celery_task_mock).start()

    # Assert
    source_connector_mock.find_patients.assert_called_once()
    assert Popen_mock.call_args[0][0][0] == "7z"
    assert Popen_mock.call_count == 2

    assert status == task.status
    assert status == MyTransferTask.Status.SUCCESS
