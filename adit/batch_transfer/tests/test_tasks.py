from unittest.mock import patch, Mock
from django.test import TestCase
from main.models import TransferJob
from main.factories import DicomServerFactory
from main.utils.scheduler import Scheduler
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferRequest
from ..tasks import batch_transfer


class BatchTransferTest(TestCase):
    @patch("batch_transfer.tasks.update_job_status.s")
    @patch("batch_transfer.tasks.chord")
    @patch("batch_transfer.tasks.transfer_request.s")
    @patch.object(Scheduler, "must_be_scheduled", return_value=False)
    def test_perform_batch_transfer_finished_with_success(  # pylint: disable=no-self-use
        self,
        must_be_scheduled_mock,
        transfer_request_mock,
        chord_mock,
        update_job_status_mock,
    ):
        job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=TransferJob.Status.PENDING,
        )
        request = BatchTransferRequestFactory(
            job=job, status=BatchTransferRequest.Status.SUCCESS
        )

        transfer_request_sig_mock = Mock()
        transfer_request_mock.return_value = transfer_request_sig_mock

        header_mock = Mock()
        chord_mock.return_value = header_mock

        update_job_status_sig_mock = Mock()
        update_job_status_mock.return_value = update_job_status_sig_mock

        batch_transfer(job.id)

        must_be_scheduled_mock.assert_called_once()
        transfer_request_mock.assert_called_once_with((request.id,), eta=None)
        chord_mock.assert_called_once_with([transfer_request_sig_mock])
        update_job_status_mock.assert_called_once_with(job.id)
        header_mock.assert_called_once_with(update_job_status_sig_mock)
