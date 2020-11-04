from unittest.mock import patch, Mock, create_autospec
import pytest
from adit.core.models import TransferJob, TransferTask
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.factories import DicomServerFactory
from adit.core.utils.scheduler import Scheduler
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferJob, BatchTransferRequest
from ..tasks import batch_transfer, transfer_request


@pytest.mark.django_db
@patch("adit.batch_transfer.tasks.on_job_failed")
@patch("adit.batch_transfer.tasks.on_job_finished")
@patch("adit.batch_transfer.tasks.chord")
@patch("adit.batch_transfer.tasks.transfer_request")
def test_batch_transfer_finished_with_success(
    transfer_request_mock,
    chord_mock,
    on_job_finished_mock,
    on_job_failed_mock,
):
    # Arrange
    job = BatchTransferJobFactory(
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        status=TransferJob.Status.PENDING,
    )
    request = BatchTransferRequestFactory(
        job=job, status=BatchTransferRequest.Status.PENDING
    )

    transfer_request_s_mock = Mock()
    transfer_request_mock.s.return_value = transfer_request_s_mock

    header_mock = Mock()
    chord_mock.return_value = header_mock

    on_job_finished_s_mock = Mock()
    on_job_finished_mock.s.return_value = on_job_finished_s_mock
    on_job_finished_on_error_mock = Mock()
    on_job_finished_s_mock.on_error.return_value = on_job_finished_on_error_mock

    on_job_failed_mock_s_mock = Mock()
    on_job_failed_mock.s.return_value = on_job_failed_mock_s_mock

    # Act
    batch_transfer(job.id)

    # Assert
    transfer_request_mock.s.assert_called_once_with(request.id)
    chord_mock.assert_called_once_with([transfer_request_s_mock])
    on_job_finished_mock.s.assert_called_once_with(job.id)
    on_job_failed_mock.s.assert_called_once_with(job_id=job.id)
    header_mock.assert_called_once_with(on_job_finished_on_error_mock)


@pytest.mark.django_db
@patch.object(Scheduler, "must_be_scheduled", return_value=False)
@patch("adit.core.tasks.transfer_dicoms")
@patch("adit.batch_transfer.tasks._fetch_patient_id")
def test_request_without_study_fails(
    fetch_patient_id_mock,
    transfer_dicoms_mock,
    must_be_scheduled_mock,
):
    # Arrange
    job = BatchTransferJobFactory(
        status=TransferJob.Status.PENDING,
    )
    request = BatchTransferRequestFactory(
        job=job, status=BatchTransferRequest.Status.PENDING
    )

    patient = {
        "PatientID": "1234",
        "PatientName": "John^Doe",
        "PatientBirthDate": "19801230",
    }
    connector = create_autospec(DicomConnector)
    connector.find_patients.return_value = [patient]
    connector.find_studies.return_value = []

    fetch_patient_id_mock.return_value = patient["PatientID"]
    transfer_dicoms_mock.return_value = TransferTask.Status.SUCCESS

    with patch.object(BatchTransferJob, "source") as source_mock:
        source_mock.dicomserver.create_connector.return_value = connector

        # Act
        # pylint: disable=no-value-for-parameter
        result = transfer_request(request.id)

        # Assert
        request.refresh_from_db()
        assert result == BatchTransferRequest.Status.WARNING
        assert result == request.status
        assert request.message == "No studies found to transfer."
        source_mock.dicomserver.create_connector.assert_called_once()
        must_be_scheduled_mock.assert_called_once()
