from unittest.mock import patch, create_autospec, ANY
import pytest
from adit.core.utils.dicom_connector import DicomConnector
from ..factories import (
    TransferTaskFactory,
    TransferJobFactory,
    DicomServerFactory,
    DicomFolderFactory,
)
from ..models import TransferJob, TransferTask, DicomServer
from ..tasks import transfer_dicoms


@pytest.fixture
def create_task(db):
    def _create_task(job):
        return TransferTaskFactory(
            job=job,
            patient_id=10001,
            study_uid="1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
            series_uids=[],
            pseudonym="",
            status=TransferTask.Status.PENDING,
            message="",
        )

    return _create_task


@pytest.fixture
def create_transfer_job(db, create_task):
    def _create_transfer_job(destination, archive_password=""):
        job = TransferJobFactory(
            status=TransferJob.Status.PENDING,
            source=DicomServerFactory(),
            destination=destination,
            archive_password=archive_password,
        )
        create_task(job)
        return job

    return _create_transfer_job


@pytest.fixture
def create_study():
    def _create_study(task):
        return {
            "PatientID": task.patient_id,
            "StudyInstanceUID": task.study_uid,
            "StudyDate": "20201001",
            "StudyTime": "0800",
            "ModalitiesInStudy": ["CT", "SR"],
        }

    return _create_study


def test_transfer_task_to_folder_with_study_succeeds(create_transfer_job, create_study):
    # Arrange
    task = create_transfer_job(DicomFolderFactory()).tasks.first()
    study = create_study(task)
    source_connector = create_autospec(DicomConnector)
    source_connector.find_studies.return_value = [study]

    with patch.object(DicomServer, "create_connector", return_value=source_connector):
        # Act
        transfer_dicoms(task.id)

    # Assert
    source_connector.download_study.assert_called_with(
        task.patient_id, task.study_uid, ANY, modifier_callback=ANY
    )
    download_path = source_connector.download_study.call_args[0][2]
    assert download_path.match(
        f"{study['PatientID']}/"
        f"{study['StudyDate']}-{study['StudyTime']}-{','.join(study['ModalitiesInStudy'])}"
    )


def test_transfer_task_to_server_with_study_succeeds(create_transfer_job, create_study):
    # Arrange
    task = create_transfer_job(DicomServerFactory()).tasks.first()
    study = create_study(task)
    source_connector = create_autospec(DicomConnector)
    source_connector.find_studies.return_value = [study]
    dest_connector = create_autospec(DicomConnector)

    with patch.object(
        DicomServer, "create_connector", side_effect=[source_connector, dest_connector]
    ):
        # Act
        transfer_dicoms(task.id)

    # Assert
    source_connector.download_study.assert_called_with(
        task.patient_id, task.study_uid, ANY, modifier_callback=ANY
    )
    download_path = source_connector.download_study.call_args[0][2]
    assert download_path.match(
        f"{study['PatientID']}/"
        f"{study['StudyDate']}-{study['StudyTime']}-{','.join(study['ModalitiesInStudy'])}"
    )
    upload_path = dest_connector.upload_folder.call_args[0][0]
    assert upload_path.match(f"*/{study['PatientID']}")


@patch("subprocess.Popen")
def test_transfer_task_to_archive_with_study_succeeds(
    Popen, create_transfer_job, create_study
):
    # Arrange
    task = create_transfer_job(DicomFolderFactory(), "foobar").tasks.first()
    study = create_study(task)
    source_connector = create_autospec(DicomConnector)
    source_connector.find_studies.return_value = [study]
    Popen().returncode = 0
    Popen().communicate.return_value = ("", "")

    with patch.object(DicomServer, "create_connector", return_value=source_connector):
        # Act
        transfer_dicoms(task.id)

    # Assert
    source_connector.download_study.assert_called_with(
        task.patient_id, task.study_uid, ANY, modifier_callback=ANY
    )
    download_path = source_connector.download_study.call_args[0][2]
    assert download_path.match(
        f"{study['PatientID']}/"
        f"{study['StudyDate']}-{study['StudyTime']}-{','.join(study['ModalitiesInStudy'])}"
    )
    assert Popen.call_args[0][0][0] == "7z"
