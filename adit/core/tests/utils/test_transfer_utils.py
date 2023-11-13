import pytest
import time_machine
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.accounts.factories import UserFactory

from ...factories import (
    DicomFolderFactory,
    DicomServerFactory,
)
from ...models import TransferJob, TransferTask
from ...utils.dicom_dataset import ResultDataset
from ...utils.dicom_operator import DicomOperator
from ...utils.transfer_utils import TransferExecutor
from ..example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory


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
    grant_access,
    create_resources,
):
    # Arrange
    job = ExampleTransferJobFactory.create(
        status=TransferJob.Status.PENDING,
        archive_password="",
    )
    task = ExampleTransferTaskFactory.create(
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        status=TransferTask.Status.PENDING,
        series_uids=[],
        pseudonym="",
        job=job,
    )
    grant_access(job.owner, task.source, "source")
    grant_access(job.owner, task.destination, "destination")

    patient, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_patients.return_value = iter([patient])
    source_operator_mock.find_studies.return_value = iter([study])
    dest_operator_mock = mocker.create_autospec(DicomOperator)

    executor = TransferExecutor(task)
    mocker.patch.object(executor, "source_operator", source_operator_mock)
    mocker.patch.object(executor, "dest_operator", dest_operator_mock)

    # Act
    (status, message, logs) = executor.start()

    # Assert
    source_operator_mock.download_study.assert_called_with(
        task.patient_id,
        task.study_uid,
        mocker.ANY,
        modifier=mocker.ANY,
    )

    upload_path = dest_operator_mock.upload_instances.call_args.args[0]
    assert upload_path.match(f"*/{study.PatientID}")

    assert status == TransferTask.Status.SUCCESS
    assert message == "Transfer task completed successfully."
    assert logs == []


@pytest.mark.django_db
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_succeeds(
    mocker: MockerFixture,
    grant_access,
    create_resources,
):
    # Arrange
    user = UserFactory.create(username="kai")
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
    grant_access(job.owner, task.source, "source")
    grant_access(job.owner, task.destination, "destination")

    patient, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_patients.return_value = iter([patient])
    source_operator_mock.find_studies.return_value = iter([study])

    executor = TransferExecutor(task)
    mocker.patch.object(executor, "source_operator", source_operator_mock)

    mocker.patch("adit.core.utils.transfer_utils.os.mkdir", autospec=True)

    # Act
    (status, message, logs) = executor.start()

    # Assert
    download_path = source_operator_mock.download_study.call_args.kwargs["dest_folder"]
    assert download_path.match(
        rf"adit_{job._meta.app_label}_{job.id}_20200101_kai/1001/20190923-080000-CT"
    )

    assert status == TransferTask.Status.SUCCESS
    assert message == "Transfer task completed successfully."
    assert logs == []


@pytest.mark.django_db
def test_transfer_to_archive_succeeds(
    mocker: MockerFixture,
    grant_access,
    create_resources,
):
    # Arrange
    job = ExampleTransferJobFactory.create(
        status=TransferJob.Status.PENDING,
        archive_password="mysecret",
    )
    task = ExampleTransferTaskFactory.create(
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        status=TransferTask.Status.PENDING,
        series_uids=[],
        pseudonym="",
        job=job,
    )
    grant_access(job.owner, task.source, "source")
    grant_access(job.owner, task.destination, "destination")

    patient, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_patients.return_value = iter([patient])
    source_operator_mock.find_studies.return_value = iter([study])

    executor = TransferExecutor(task)
    mocker.patch.object(executor, "source_operator", source_operator_mock)

    Popen_mock = mocker.patch("subprocess.Popen")
    Popen_mock.return_value.returncode = 0
    Popen_mock.return_value.communicate.return_value = ("", "")

    # Act
    (status, message, logs) = executor.start()

    # Assert
    source_operator_mock.find_patients.assert_called_once()
    assert Popen_mock.call_args.args[0][0] == "7z"
    assert Popen_mock.call_count == 2

    assert status == TransferTask.Status.SUCCESS
    assert message == "Transfer task completed successfully."
    assert logs == []
