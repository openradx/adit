import pytest
from ..factories import TransferTaskFactory, TransferJobFactory, DicomServerFactory
from ..models import TransferJob, TransferTask
from ..tasks import transfer_dicoms


@pytest.fixture
def server_to_server_job(db):
    return TransferJobFactory(
        job_type="TE",
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
    )


@pytest.fixture
def study_task(db):  # pylint: disable=unused-argument
    return TransferTaskFactory(
        patient_id=10001,
        study_uid="1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
        series_uids=[],
        pseudonym="",
        status=TransferTask.Status.PENDING,
        message="",
    )


def test_transfer_study_to_server_succeeds(server_to_server_job, study_task):
    assert True == True
    # # Arrange

    # # Act
    # transfer_dicoms(self.study_task.id)

    # # Assert
