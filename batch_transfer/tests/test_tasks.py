from django.test import TestCase
from unittest.mock import patch
from datetime import time
from main.models import DicomJob
from main.factories import DicomServerFactory, DicomFolderFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferRequest
from ..utils.batch_handler import BatchHandler
from .. import tasks

class BatchTransferTasksTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.batch_job_with_server_dest = BatchTransferJobFactory()

    @patch.object(BatchHandler, 'batch_transfer', return_value=True)
    def test_batch_transfer_task_completed(self, handler_batch_transfer_mock):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        BatchTransferRequestFactory(job=batch_job)

        tasks.batch_transfer_task(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertEqual(batch_job.status, DicomJob.Status.COMPLETED)

    @patch.object(BatchHandler, 'batch_transfer', return_value=False)
    def test_batch_transfer_task_not_completed(self, handler_batch_transfer_mock):
        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        BatchTransferRequestFactory(job=batch_job)

        tasks.batch_transfer_task(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertNotEqual(batch_job.status, DicomJob.Status.COMPLETED)

    def test_is_time_between(self):
        params = (
            (time(1, 0), time(3, 0), time(2, 0)),
            (time(1, 0), time(3, 0), time(1, 0)),
            (time(1, 0), time(3, 0), time(3, 0)),
            (time(23, 0), time(1, 0), time(0, 0)),
        )
        for param in params:
            self.assertEqual(tasks._is_time_between(param[0], param[1], param[2]), True)

    def test_is_time_not_between(self):
        params = (
            (time(1, 0), time(3, 0), time(0, 0)),
            (time(1, 0), time(3, 0), time(4, 0)),
            (time(23, 0), time(1, 0), time(22, 0)),
            (time(23, 0), time(1, 0), time(2, 0)),
        )
        for param in params:
            self.assertEqual(tasks._is_time_between(param[0], param[1], param[2]), False)
