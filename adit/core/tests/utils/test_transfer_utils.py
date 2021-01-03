from unittest.mock import patch, create_autospec, ANY
import datetime
import pytest
from django.db import connection
from django.db.utils import ProgrammingError
from django.db.models.base import ModelBase
from ...models import TransferJob, TransferTask
from ...factories import (
    DicomServerFactory,
    DicomFolderFactory,
    TransferJobFactory,
    TransferTaskFactory,
)
from ...utils.dicom_connector import DicomConnector
from ...utils.transfer_utils import execute_transfer


@pytest.fixture(scope="session")
def setup_abstract_models(django_db_setup, django_db_blocker):
    # Solution adapted from https://stackoverflow.com/q/4281670/166229
    with django_db_blocker.unblock():
        transfer_job_model = ModelBase(
            TransferJob.__name__,
            (TransferJob,),
            {"__module__": TransferJob.__module__},
        )
        transfer_task_model = ModelBase(
            TransferTask.__name__,
            (TransferTask,),
            {"__module__": TransferTask.__module__},
        )
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(transfer_job_model)
                schema_editor.create_model(transfer_task_model)
        except ProgrammingError:
            pass

        yield transfer_job_model, transfer_task_model

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(transfer_job_model)
            schema_editor.delete_model(transfer_task_model)

        connection.close()


@pytest.fixture(scope="session")
def setup_abstract_factories(setup_abstract_models):
    TestTransferJob, TestTransferTask = setup_abstract_models

    class TestTransferJobFactory(TransferJobFactory):
        class Meta:
            model = TestTransferJob

    class TestTransferTaskFactory(TransferTaskFactory):
        class Meta:
            model = TestTransferTask

    yield TestTransferJobFactory, TestTransferTaskFactory


@pytest.mark.django_db
@patch("adit.core.utils.transfer_utils._create_dest_connector", autospec=True)
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
def test_transfer_to_server_succeeds(
    create_source_connector_mock,
    create_dest_connector_mock,
    setup_abstract_factories,
):
    # Arrange
    TestTransferJobFactory, TestTransferTaskFactory = setup_abstract_factories

    job = TestTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        archive_password="",
    )
    task = TestTransferTaskFactory(
        status=TransferTask.Status.PENDING, series_uids=[], pseudonym=""
    )
    task.job = job

    study = {
        "PatientID": task.patient_id,
        "StudyInstanceUID": task.study_uid,
        "StudyDate": datetime.date(2020, 10, 1),
        "StudyTime": datetime.time(8, 0),
        "ModalitiesInStudy": ["CT", "SR"],
    }
    source_connector_mock = create_autospec(DicomConnector)
    source_connector_mock.find_studies.return_value = [study]
    create_source_connector_mock.return_value = source_connector_mock
    dest_connector_mock = create_autospec(DicomConnector)
    create_dest_connector_mock.return_value = dest_connector_mock

    # Act
    status = execute_transfer(task)

    # Assert
    source_connector_mock.download_study.assert_called_with(
        task.patient_id, task.study_uid, ANY, modifier_callback=ANY
    )

    upload_path = dest_connector_mock.upload_folder.call_args[0][0]
    assert upload_path.match(f"*/{study['PatientID']}")

    assert status == task.status


@pytest.mark.django_db
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
def test_transfer_to_folder_succeeds(
    create_source_connector_mock, setup_abstract_factories
):
    # Arrange
    TestTransferJobFactory, TestTransferTaskFactory = setup_abstract_factories
    job = TestTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="",
    )
    task = TestTransferTaskFactory(
        status=TransferTask.Status.PENDING,
        series_uids=[],
        pseudonym="",
    )
    task.job = job

    study = {
        "PatientID": task.patient_id,
        "StudyInstanceUID": task.study_uid,
        "StudyDate": datetime.date(2020, 10, 1),
        "StudyTime": datetime.time(8, 0),
        "ModalitiesInStudy": ["CT", "SR"],
    }
    source_connector_mock = create_autospec(DicomConnector)
    source_connector_mock.find_studies.return_value = [study]
    create_source_connector_mock.return_value = source_connector_mock

    # Act
    with patch("adit.core.utils.transfer_utils.Path.mkdir", autospec=True):
        status = execute_transfer(task)

    # Assert
    download_path = source_connector_mock.download_study.call_args[0][2]
    assert download_path.match(
        f"{study['PatientID']}/"
        f"{study['StudyDate'].strftime('%Y%m%d')}"
        f"-{study['StudyTime'].strftime('%H%M%S')}"
        f"-{','.join(study['ModalitiesInStudy'])}"
    )

    assert status == task.status


@pytest.mark.django_db
@patch("subprocess.Popen")
@patch("adit.core.utils.transfer_utils._create_source_connector", autospec=True)
def test_transfer_to_archive_succeeds(
    create_source_connector_mock, Popen_mock, setup_abstract_factories
):
    # Arrange
    TestTransferJobFactory, TestTransferTaskFactory = setup_abstract_factories
    job = TestTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="mysecret",
    )
    task = TestTransferTaskFactory(
        status=TransferTask.Status.PENDING, series_uids=[], pseudonym=""
    )
    task.job = job

    study = {
        "PatientID": task.patient_id,
        "StudyInstanceUID": task.study_uid,
        "StudyDate": datetime.date(2020, 10, 1),
        "StudyTime": datetime.time(8, 0),
        "ModalitiesInStudy": ["CT", "SR"],
    }
    source_connector_mock = create_autospec(DicomConnector)
    source_connector_mock.find_studies.return_value = [study]
    create_source_connector_mock.return_value = source_connector_mock

    Popen_mock().returncode = 0
    Popen_mock().communicate.return_value = ("", "")

    # Act
    status = execute_transfer(task)

    # Assert
    assert Popen_mock.call_args[0][0][0] == "7z"

    assert status == task.status
