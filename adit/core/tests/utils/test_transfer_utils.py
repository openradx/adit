from unittest.mock import ANY, create_autospec, patch

import pytest
import time_machine
from celery import Task as CeleryTask
from pydicom import Dataset

from adit.core.utils.dicom_dataset import ResultDataset
from adit.shared.accounts.factories import UserFactory

from ...factories import (
    DicomFolderFactory,
    DicomServerFactory,
)
from ...models import TransferJob, TransferTask
from ...utils.dicom_operator import DicomOperator
from ...utils.transfer_utils import TransferExecutor
from ..conftest import ExampleModels


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
@patch("adit.core.utils.transfer_utils._create_dest_operator", autospec=True)
@patch("adit.core.utils.transfer_utils._create_source_operator", autospec=True)
def test_transfer_to_server_succeeds(
    create_source_operator_mock,
    create_dest_operator_mock,
    example_models: ExampleModels,
    grant_access,
    create_resources,
):
    # Arrange
    job = example_models.transfer_job_factory_class.create(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        archive_password="",
    )
    task = example_models.transfer_task_factory_class.create(
        status=TransferTask.Status.PENDING,
        series_uids="",
        pseudonym="",
        job=job,
    )
    grant_access(job.owner, job.source, "source")
    grant_access(job.owner, job.destination, "destination")

    patient, study = create_resources(task)

    source_operator_mock = create_autospec(DicomOperator)
    source_operator_mock.find_patients.return_value = iter([patient])
    source_operator_mock.find_studies.return_value = iter([study])
    create_source_operator_mock.return_value = source_operator_mock
    dest_operator_mock = create_autospec(DicomOperator)
    create_dest_operator_mock.return_value = dest_operator_mock

    celery_task_mock = create_autospec(CeleryTask)

    # Act
    (status, message) = TransferExecutor(task, celery_task_mock).start()

    # Assert
    source_operator_mock.download_study.assert_called_with(
        task.patient_id,
        task.study_uid,
        ANY,
        modifier=ANY,
    )

    upload_path = dest_operator_mock.upload_instances.call_args.args[0]
    assert upload_path.match(f"*/{study.PatientID}")

    assert status == TransferTask.Status.SUCCESS
    assert message == "Transfer task completed successfully."


@pytest.mark.django_db
@patch("adit.core.utils.transfer_utils._create_source_operator", autospec=True)
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_succeeds(
    create_source_operator_mock,
    example_models: ExampleModels,
    grant_access,
    create_resources,
):
    # Arrange
    user = UserFactory.create(username="kai")
    job = example_models.transfer_job_factory_class.create(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="",
        owner=user,
    )
    task = example_models.transfer_task_factory_class.create(
        status=TransferTask.Status.PENDING,
        patient_id="1001",
        series_uids="",
        pseudonym="",
        job=job,
    )
    grant_access(job.owner, job.source, "source")
    grant_access(job.owner, job.destination, "destination")

    patient, study = create_resources(task)

    source_operator_mock = create_autospec(DicomOperator)
    source_operator_mock.find_patients.return_value = iter([patient])
    source_operator_mock.find_studies.return_value = iter([study])
    create_source_operator_mock.return_value = source_operator_mock

    celery_task_mock = create_autospec(CeleryTask)

    # Act
    with patch("adit.core.utils.transfer_utils.os.mkdir", autospec=True):
        (status, message) = TransferExecutor(task, celery_task_mock).start()

    # Assert
    download_path = source_operator_mock.download_study.call_args.kwargs["dest_folder"]
    assert download_path.match(r"adit_adit.core_1_20200101_kai/1001/20190923-080000-CT")

    assert status == TransferTask.Status.SUCCESS
    assert message == "Transfer task completed successfully."


@pytest.mark.django_db
@patch("subprocess.Popen")
@patch("adit.core.utils.transfer_utils._create_source_operator", autospec=True)
def test_transfer_to_archive_succeeds(
    create_source_operator_mock,
    Popen_mock,
    example_models: ExampleModels,
    grant_access,
    create_resources,
):
    # Arrange
    job = example_models.transfer_job_factory_class.create(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        archive_password="mysecret",
    )
    task = example_models.transfer_task_factory_class.create(
        status=TransferTask.Status.PENDING, series_uids="", pseudonym="", job=job
    )
    grant_access(job.owner, job.source, "source")
    grant_access(job.owner, job.destination, "destination")

    patient, study = create_resources(task)

    source_operator_mock = create_autospec(DicomOperator)
    source_operator_mock.find_patients.return_value = iter([patient])
    source_operator_mock.find_studies.return_value = iter([study])
    create_source_operator_mock.return_value = source_operator_mock

    Popen_mock.return_value.returncode = 0
    Popen_mock.return_value.communicate.return_value = ("", "")

    celery_task_mock = create_autospec(CeleryTask)

    # Act
    (status, message) = TransferExecutor(task, celery_task_mock).start()

    # Assert
    source_operator_mock.find_patients.assert_called_once()
    assert Popen_mock.call_args.args[0][0] == "7z"
    assert Popen_mock.call_count == 2

    assert status == TransferTask.Status.SUCCESS
    assert message == "Transfer task completed successfully."
