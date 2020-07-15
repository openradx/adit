from django.test import TestCase
from unittest.mock import patch
from main.factories import DicomServerFactory, DicomFolderFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..jobs import BatchHandler
from ..jobs import batch_transfer

class BackgroundJobTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.batch_job_with_server_dest = BatchTransferJobFactory()

    @patch.object(BatchHandler, 'batch_transfer')
    def test_batch_transfer_to_folder(self, handler_batch_transfer_mock):
        batch_job = BatchTransferJobFactory(
            source = DicomServerFactory(),
            destination = DicomServerFactory()
        )
        BatchTransferRequestFactory(job=batch_job)
        BatchTransferRequestFactory(job=batch_job)

        batch_transfer(batch_job.id)

        handler_batch_transfer_mock.assert_called_once()