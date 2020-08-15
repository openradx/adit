from unittest.mock import patch
from django.test import TestCase
from main.models import TransferJob
from main.factories import DicomServerFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferRequest
from ..utils.batch_handler import BatchHandler
from ..tasks import perform_batch_transfer


class BatchTransferTaskTest(TestCase):
    @patch.object(BatchHandler, "batch_transfer", return_value=True)
    def test_perform_batch_transfer_finished_with_success(
        self, handler_batch_transfer_mock
    ):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=TransferJob.Status.PENDING,
        )
        BatchTransferRequestFactory(
            job=batch_job, status=BatchTransferRequest.Status.SUCCESS
        )

        perform_batch_transfer(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, TransferJob.Status.SUCCESS)

    @patch.object(BatchHandler, "batch_transfer", return_value=True)
    def test_perform_batch_transfer_finished_with_warning(
        self, handler_batch_transfer_mock
    ):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=TransferJob.Status.PENDING,
        )
        BatchTransferRequestFactory(
            job=batch_job, status=BatchTransferRequest.Status.FAILURE
        )
        BatchTransferRequestFactory(
            job=batch_job, status=BatchTransferRequest.Status.SUCCESS
        )

        perform_batch_transfer(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, TransferJob.Status.WARNING)

    @patch.object(BatchHandler, "batch_transfer", return_value=True)
    def test_perform_batch_transfer_finished_with_failure(
        self, handler_batch_transfer_mock
    ):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=TransferJob.Status.PENDING,
        )
        BatchTransferRequestFactory(
            job=batch_job, status=BatchTransferRequest.Status.FAILURE
        )

        perform_batch_transfer(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, TransferJob.Status.FAILURE)

    def test_perform_batch_transfer_paused(self):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=TransferJob.Status.PENDING,
        )
        BatchTransferRequestFactory(job=batch_job)

        # We have to alter the instance in the handler and not the instance
        # in the test function (those are different instances of the same
        # database object). For that we access the partial.
        def simulate_callback(*args):
            # args[2] is the partial and args[0] the parameter
            batch_job_in_handler = args[2].args[0]
            batch_job_in_handler.status = TransferJob.Status.PAUSED
            batch_job_in_handler.save()
            return False

        with patch.object(BatchHandler, "batch_transfer", new=simulate_callback):
            perform_batch_transfer(batch_job.id)

        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, TransferJob.Status.PAUSED)
