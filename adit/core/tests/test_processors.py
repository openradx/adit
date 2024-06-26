import pytest
import time_machine
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.auth_utils import add_user_to_group
from pydicom import Dataset
from pytest_mock import MockerFixture

from ..factories import (
    DicomFolderFactory,
    DicomServerFactory,
)
from ..models import TransferJob, TransferTask
from ..processors import TransferTaskProcessor
from ..utils.auth_utils import grant_access
from ..utils.dicom_dataset import ResultDataset
from ..utils.dicom_operator import DicomOperator
from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory


@pytest.fixture
def create_resources():
    def _create_resources(transfer_task):
        ds = Dataset()
        ds.PatientID = transfer_task.patient_id
        patient = ResultDataset(ds)

        ds = Dataset()
        ds.PatientID = transfer_task.patient_id
        ds.StudyInstanceUID = transfer_task.study_uid
        ds.StudyDate = "20190923"
        ds.StudyTime = "080000"
        ds.ModalitiesInStudy = ["CT", "SR"]
        study = ResultDataset(ds)

        return patient, study

    return _create_resources


@pytest.mark.django_db
def test_transfer_to_server_succeeds(
    mocker: MockerFixture,
    example_transfer_group,
    create_resources,
):
    # Arrange
    user = UserFactory.create(username="kai")
    add_user_to_group(user, example_transfer_group)
    job = ExampleTransferJobFactory.create(
        status=TransferJob.Status.PENDING,
        archive_password="",
        owner=user,
    )
    task = ExampleTransferTaskFactory.create(
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        status=TransferTask.Status.PENDING,
        series_uids=[],
        pseudonym="",
        job=job,
    )
    grant_access(example_transfer_group, task.source, source=True)
    grant_access(example_transfer_group, task.destination, destination=True)

    patient, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([study])
    dest_operator_mock = mocker.create_autospec(DicomOperator)

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)
    mocker.patch.object(processor, "dest_operator", dest_operator_mock)

    # Act
    result = processor.process()

    # Assert
    source_operator_mock.fetch_study.assert_called_with(task.patient_id, task.study_uid, mocker.ANY)

    upload_path = dest_operator_mock.upload_instances.call_args.args[0]
    assert upload_path.match(f"*/{study.PatientID}")

    assert result["status"] == TransferTask.Status.SUCCESS
    assert result["message"] == "Transfer task completed successfully."
    assert result["log"] == ""


@pytest.mark.django_db
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_succeeds(
    mocker: MockerFixture,
    example_transfer_group,
    create_resources,
):
    # Arrange
    user = UserFactory.create(username="kai")
    add_user_to_group(user, example_transfer_group)
    job = ExampleTransferJobFactory.create(
        status=TransferJob.Status.PENDING,
        archive_password="",
        owner=user,
    )
    task = ExampleTransferTaskFactory.create(
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        status=TransferTask.Status.PENDING,
        patient_id="1001",
        series_uids=[],
        pseudonym="",
        job=job,
    )
    grant_access(example_transfer_group, task.source, source=True)
    grant_access(example_transfer_group, task.destination, destination=True)

    patient, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([study])

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)

    mocker.patch("adit.core.processors.os.mkdir", autospec=True)

    # Act
    result = processor.process()

    # Assert
    source_operator_mock.fetch_study.assert_called_with(task.patient_id, task.study_uid, mocker.ANY)

    assert result["status"] == TransferTask.Status.SUCCESS
    assert result["message"] == "Transfer task completed successfully."
    assert result["log"] == ""


@pytest.mark.django_db
def test_transfer_to_archive_succeeds(
    mocker: MockerFixture,
    example_transfer_group,
    create_resources,
):
    # Arrange
    user = UserFactory.create(username="kai")
    add_user_to_group(user, example_transfer_group)
    job = ExampleTransferJobFactory.create(
        status=TransferJob.Status.PENDING,
        archive_password="mysecret",
        owner=user,
    )
    task = ExampleTransferTaskFactory.create(
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        status=TransferTask.Status.PENDING,
        series_uids=[],
        pseudonym="",
        job=job,
    )
    grant_access(example_transfer_group, task.source, source=True)
    grant_access(example_transfer_group, task.destination, destination=True)

    patient, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([study])

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)

    Popen_mock = mocker.patch("subprocess.Popen")
    Popen_mock.return_value.returncode = 0
    Popen_mock.return_value.communicate.return_value = ("", "")

    # Act
    result = processor.process()

    # Assert
    assert Popen_mock.call_args.args[0][0] == "7z"
    assert Popen_mock.call_count == 2

    assert result["status"] == TransferTask.Status.SUCCESS
    assert result["message"] == "Transfer task completed successfully."
    assert result["log"] == ""
