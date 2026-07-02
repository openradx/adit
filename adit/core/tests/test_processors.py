import pytest
import time_machine
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import UID
from pytest_mock import MockerFixture

from adit.core.errors import DicomError
from adit.core.factories import (
    DicomFolderFactory,
    DicomServerFactory,
)
from adit.core.models import TransferJob, TransferTask
from adit.core.processors import TransferTaskProcessor
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.testing_helpers import create_example_transfer_group, create_resources

from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory


def _make_series(series_uid: str, modality: str) -> ResultDataset:
    ds = Dataset()
    ds.SeriesInstanceUID = series_uid
    ds.SeriesNumber = 1
    ds.Modality = modality
    return ResultDataset(ds)


@pytest.mark.django_db
def test_transfer_to_server_succeeds(mocker: MockerFixture):
    # Arrange
    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
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
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    _, study = create_resources(task)

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

    upload_path = dest_operator_mock.upload_images.call_args.args[0]
    assert upload_path.match(f"*/{study.PatientID}")

    assert result["status"] == TransferTask.Status.SUCCESS
    assert result["message"] == "Transfer task completed successfully."
    assert result["log"] == ""


@pytest.mark.django_db
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_succeeds(mocker: MockerFixture):
    # Arrange
    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
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
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    _, study = create_resources(task)

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
def test_transfer_to_archive_succeeds(mocker: MockerFixture):
    # Arrange
    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
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
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    _, study = create_resources(task)

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


@pytest.mark.django_db
def test_transfer_to_server_fails_when_study_not_found(mocker: MockerFixture):
    # Arrange: source returns no studies for the requested Study Instance UID,
    # neither on the PatientID+StudyUID query nor on the StudyUID-only fallback.
    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
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
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([])
    dest_operator_mock = mocker.create_autospec(DicomOperator)

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)
    mocker.patch.object(processor, "dest_operator", dest_operator_mock)

    # Act / Assert: process() surfaces the failure as a DicomError (the task runner
    # in tasks.py maps this to TransferTask.Status.FAILURE). Nothing is uploaded.
    with pytest.raises(DicomError, match="No study found"):
        processor.process()

    dest_operator_mock.upload_images.assert_not_called()


@pytest.mark.django_db
def test_transfer_to_server_fails_when_fetch_raises(mocker: MockerFixture):
    # Arrange: the study is found but fetching the images fails (e.g. PACS error).
    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
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
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    _, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([study])
    source_operator_mock.fetch_study.side_effect = DicomError("Connection to PACS failed.")
    dest_operator_mock = mocker.create_autospec(DicomOperator)

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)
    mocker.patch.object(processor, "dest_operator", dest_operator_mock)

    mocker.patch("adit.core.processors.os.makedirs", autospec=True)

    # Act / Assert: the fetch error propagates out of process() and the destination
    # is never uploaded to.
    with pytest.raises(DicomError, match="Connection to PACS failed."):
        processor.process()

    dest_operator_mock.upload_images.assert_not_called()


@pytest.mark.django_db
@time_machine.travel("2020-01-01")
def test_partial_study_failure_yields_warning_status(mocker: MockerFixture):
    # Arrange: the transfer itself completes, but the source operator recorded a
    # warning (e.g. some images of the study could not be fetched with C-MOVE,
    # see DicomOperator._fetch_images_with_c_move). The processor folds operator
    # logs into the result and must downgrade the status to WARNING.
    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
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
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    _, study = create_resources(task)

    warning_log = {
        "level": "Warning",
        "title": "Some images could not be fetched",
        "message": "Failed to fetch some images with C-MOVE.",
    }

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([study])
    source_operator_mock.get_logs.return_value = [warning_log]

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)

    mocker.patch("adit.core.processors.os.makedirs", autospec=True)

    # Act
    result = processor.process()

    # Assert: status is downgraded to WARNING, the message carries the warning
    # title, and the warning message is recorded in the log.
    assert result["status"] == TransferTask.Status.WARNING
    assert result["message"] == "Some images could not be fetched"
    assert "Failed to fetch some images with C-MOVE." in result["log"]


@pytest.mark.django_db
@time_machine.travel("2020-01-01")
def test_transfer_to_folder_pseudonymizes_dataset(mocker: MockerFixture):
    # Arrange: a pseudonymized whole-study transfer to a folder. The processor
    # transfers on the series level (to honor EXCLUDE_MODALITIES) and runs each
    # fetched dataset through the real DicomManipulator/Pseudonymizer before
    # writing it. We capture what gets written and assert it is pseudonymized.
    pseudonym = "SECRET01"

    user = UserFactory.create(username="kai")
    group = create_example_transfer_group()
    add_user_to_group(user, group)
    job = ExampleTransferJobFactory.create(
        status=TransferJob.Status.PENDING,
        archive_password="",
        trial_protocol_id="",
        trial_protocol_name="",
        owner=user,
    )
    task = ExampleTransferTaskFactory.create(
        source=DicomServerFactory(),
        destination=DicomFolderFactory(),
        status=TransferTask.Status.PENDING,
        patient_id="1001",
        series_uids=[],
        pseudonym=pseudonym,
        job=job,
    )
    grant_access(group, task.source, source=True)
    grant_access(group, task.destination, destination=True)

    _, study = create_resources(task)

    source_operator_mock = mocker.create_autospec(DicomOperator)
    source_operator_mock.find_studies.return_value = iter([study])
    # Pseudonymized whole-study transfer queries series of the study (CT is kept,
    # SR would be excluded but is not present here).
    source_operator_mock.find_series.return_value = iter(
        [_make_series("1.2.3.4.5", "CT")]
    )

    # The original (identifiable) image that the PACS would deliver.
    original = Dataset()
    original.PatientID = "1001"
    original.PatientName = "Doe^John"
    original.StudyInstanceUID = study.StudyInstanceUID
    original.SeriesInstanceUID = "1.2.3.4.5"
    original.SOPInstanceUID = "1.2.3.4.5.6"
    original.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    original.SeriesNumber = 1
    original.Modality = "CT"
    original.StudyDate = "20190923"
    original.StudyTime = "080000"
    # file_meta is required by dicognito (the underlying anonymizer).
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = UID(original.SOPClassUID)
    file_meta.MediaStorageSOPInstanceUID = UID(original.SOPInstanceUID)
    file_meta.TransferSyntaxUID = UID("1.2.840.10008.1.2")  # Implicit VR Little Endian
    original.file_meta = file_meta

    def fetch_series_side_effect(patient_id, study_uid, series_uid, callback):
        callback(original)

    source_operator_mock.fetch_series.side_effect = fetch_series_side_effect

    processor = TransferTaskProcessor(task)
    mocker.patch.object(processor, "source_operator", source_operator_mock)

    # Avoid touching the (faked, read-only) destination folder path.
    mocker.patch("adit.core.processors.os.makedirs", autospec=True)
    mocker.patch("adit.core.processors.Path.mkdir", autospec=True)

    # Capture the dataset handed to write_dataset (real pseudonymization already ran).
    write_mock = mocker.patch("adit.core.processors.write_dataset", autospec=True)

    # Act
    result = processor.process()

    # Assert: a dataset was written and it is actually pseudonymized.
    assert result["status"] == TransferTask.Status.SUCCESS
    write_mock.assert_called_once()
    written_ds = write_mock.call_args.args[0]
    assert written_ds.PatientID == pseudonym
    assert written_ds.PatientName == pseudonym
    # The anonymizer must have rewritten the PatientName away from the original.
    assert str(written_ds.PatientName) != "Doe^John"
    # The fetched-image callback ran on the series level (pseudonymization path),
    # not as a whole-study fetch.
    source_operator_mock.fetch_study.assert_not_called()
    source_operator_mock.fetch_series.assert_called_once()
