from django.test import TestCase
from unittest.mock import patch
from datetime import time, datetime
import time_machine
import django_rq
from main.models import DicomJob
from main.factories import DicomServerFactory, DicomFolderFactory
from ..factories import BatchTransferJobFactory, BatchTransferRequestFactory
from ..models import BatchTransferRequest
from ..utils.batch_handler import BatchHandler
from .. import tasks

class BatchTransferTaskUnitTest(TestCase):
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
        print(111)
        scheduler = django_rq.get_scheduler('low')
        print(dir(scheduler))
        for x in scheduler.get_jobs():
            print(x)
        print(222)

        batch_job = BatchTransferJobFactory(
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
            status=DicomJob.Status.PENDING
        )
        request1 = BatchTransferRequestFactory(job=batch_job, status=BatchTransferRequest.Status.UNPROCESSED)

        tasks.enqueue_batch_job(batch_job.id)

        django_rq.get_worker().work(burst=True)

        request1.refresh_from_db()
        print(request1.__dict__)

        print(datetime.now())

        self.assertFalse(False)

