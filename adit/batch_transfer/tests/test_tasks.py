from unittest.mock import patch, Mock, create_autospec
from django.test import TestCase
from adit.main.models import TransferJob, TransferTask
from adit.main.utils.dicom_connector import DicomConnector
from adit.main.factories import DicomServerFactory
from adit.main.utils.scheduler import Scheduler
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferJob, BatchTransferRequest
from ..tasks import batch_transfer, transfer_request


class BatchTransferTest(TestCase):
    @patch("adit.batch_transfer.tasks.update_job_status")
    @patch("adit.batch_transfer.tasks.chord")
    @patch("adit.batch_transfer.tasks.transfer_request")
    def test_batch_transfer_finished_with_success(  # pylint: disable=no-self-use
        self,
        transfer_request_mock,
        chord_mock,
        update_job_status_mock,
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

        transfer_request_signature_mock = Mock()
        transfer_request_mock.s.return_value = transfer_request_signature_mock

        header_mock = Mock()
        chord_mock.return_value = header_mock

        update_job_status_signature_mock = Mock()
        update_job_status_mock.s.return_value = update_job_status_signature_mock

        # Act
        batch_transfer(job.id)

        # Assert
        transfer_request_mock.s.assert_called_once_with(request.id)
        chord_mock.assert_called_once_with([transfer_request_signature_mock])
        update_job_status_mock.s.assert_called_once_with(job.id)
        header_mock.assert_called_once_with(update_job_status_signature_mock)


class TransferRequestTest(TestCase):
    @patch.object(Scheduler, "must_be_scheduled", return_value=False)
    @patch("adit.main.tasks.transfer_dicoms")
    def test_request_without_study_fails(
        self, transfer_dicoms_mock, must_be_scheduled_mock
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

        transfer_dicoms_mock.return_value = TransferTask.Status.SUCCESS

        with patch.object(BatchTransferJob, "source") as source_mock:
            source_mock.dicomserver.create_connector.return_value = connector

            # Act
            # pylint: disable=no-value-for-parameter
            result = transfer_request(request.id)

            # Assert
            request.refresh_from_db()
            self.assertEqual(result, BatchTransferRequest.Status.FAILURE)
            self.assertEqual(result, request.status)
            self.assertEqual(request.message, "No studies found to transfer.")
            source_mock.dicomserver.create_connector.assert_called_once()
            must_be_scheduled_mock.assert_called_once()
