from django.test import TestCase
from unittest.mock import patch
from main.factories import DicomServerFactory, DicomFolderFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..jobs import BatchTransferrer
from ..jobs import batch_transfer

class BackgroundJobTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.batch_job_with_server_dest = BatchTransferJobFactory()

    @patch.object(BatchTransferrer, 'transfer_to_server')
    def test_batch_transfer_to_folder(self, transfer_to_server_mock):
        batch_job = BatchTransferJobFactory(
            source = DicomServerFactory(),
            destination = DicomServerFactory()
        )
        BatchTransferRequestFactory(job=batch_job)
        BatchTransferRequestFactory(job=batch_job)

        batch_transfer(batch_job.id)

        transfer_to_server_mock.assert_called_once()