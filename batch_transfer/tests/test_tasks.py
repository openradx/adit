from django.test import TestCase
from unittest.mock import patch
from datetime import time, datetime
import time_machine
from main.models import DicomJob
from main.factories import DicomServerFactory, DicomFolderFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferRequest
from ..utils.batch_handler import BatchHandler
from .. import tasks

class BatchTaskTest(TestCase):
    @patch.object(BatchHandler, 'batch_transfer', return_value=True)
    def test_batch_transfer_task_finished_with_success(self, handler_batch_transfer_mock):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        BatchTransferRequestFactory(job=batch_job,
                status=BatchTransferRequest.Status.SUCCESS)

        tasks.batch_transfer_task(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, DicomJob.Status.SUCCESS)

    @patch.object(BatchHandler, 'batch_transfer', return_value=True)
    def test_batch_transfer_task_finished_with_warning(self, handler_batch_transfer_mock):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        BatchTransferRequestFactory(job=batch_job,
                status=BatchTransferRequest.Status.FAILURE)
        BatchTransferRequestFactory(job=batch_job,
                status=BatchTransferRequest.Status.SUCCESS)

        tasks.batch_transfer_task(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, DicomJob.Status.WARNING)

    @patch.object(BatchHandler, 'batch_transfer', return_value=False)
    def test_batch_transfer_task_paused(self, handler_batch_transfer_mock):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        BatchTransferRequestFactory(job=batch_job)

        # We have to alter the instance in the handler and not the instance
        # in the test function (those are different instances of the same
        # database object). For that we access the partial.
        def simulate_callback(*args):
            # args[2] is the partial and args[0] the parameter
            batch_job_in_handler = args[2].args[0]
            batch_job_in_handler.status = DicomJob.Status.PAUSED
            batch_job_in_handler.save()
            return False

        with patch.object(BatchHandler, 'batch_transfer', new=simulate_callback):
            tasks.batch_transfer_task(batch_job.id)

        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, DicomJob.Status.PAUSED)

    def test_is_time_between(self):
        params = (
            (time(1, 0), time(3, 0), time(2, 0)),
            (time(1, 0), time(3, 0), time(1, 0)),
            (time(1, 0), time(3, 0), time(3, 0)),
            (time(23, 0), time(1, 0), time(0, 0)),
        )
        for param in params:
            self.assertEqual(tasks.is_time_between(param[0], param[1], param[2]), True)

    def test_is_time_not_between(self):
        params = (
            (time(1, 0), time(3, 0), time(0, 0)),
            (time(1, 0), time(3, 0), time(4, 0)),
            (time(23, 0), time(1, 0), time(22, 0)),
            (time(23, 0), time(1, 0), time(2, 0)),
        )
        for param in params:
            self.assertEqual(tasks.is_time_between(param[0], param[1], param[2]), False)


class BatchTransferTaskIntegrationTest(TestCase):
    @time_machine.travel('2020-11-05 15:22')
    def test_enqueue_batch_job(self):

        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        request1 = BatchTransferRequestFactory(job=batch_job, status=BatchTransferRequest.Status.UNPROCESSED)

        tasks.enqueue_batch_job(batch_job.id)

        request1.refresh_from_db()

        print('TODO')

        self.assertFalse(False)