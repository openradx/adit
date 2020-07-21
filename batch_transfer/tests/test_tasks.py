from django.test import TestCase
from unittest.mock import patch
from datetime import time
from main.models import DicomJob
from main.factories import DicomServerFactory, DicomFolderFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferRequest
from ..utils.batch_handler import BatchHandler
from ..tasks import batch_transfer_task

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

        batch_transfer_task(batch_job.id)

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

        batch_transfer_task(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()
        batch_job.refresh_from_db()
        self.assertNotEqual(batch_job.status, DicomJob.Status.COMPLETED)

    def test_is_time_between(self):
        pass
