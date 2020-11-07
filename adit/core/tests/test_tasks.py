from unittest.mock import patch, create_autospec, ANY
import pytest
from adit.core.utils.dicom_connector import DicomConnector
from ..factories import TransferTaskFactory, TransferJobFactory, DicomServerFactory
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
def transfer_to_server_job(db, create_task):
    job = TransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
    )
    create_task(job)
    return job


def test_transfer_task_to_server_with_study_succeeds(transfer_to_server_job):
    # Arrange
    task = transfer_to_server_job.tasks.first()
    study = {
        "PatientID": task.patient_id,
        "StudyInstanceUID": task.study_uid,
        "StudyDate": "20201001",
        "StudyTime": "0800",
        "Modalities": ["CT", "SR"],
    }
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
        f"{study['StudyDate']}-{study['StudyTime']}-{','.join(study['Modalities'])}"
    )
    upload_path = dest_connector.upload_folder.call_args[0][0]
    assert upload_path.match(f"*/{study['PatientID']}")
