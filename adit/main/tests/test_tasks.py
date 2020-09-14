from django.test import TestCase
from ..factories import TransferTaskFactory, TransferJobFactory, DicomServerFactory
from ..models import TransferJob, TransferTask
from ..tasks import transfer_dicoms


class TransferDicomsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.server_to_server_job = TransferJobFactory(
            status=TransferJob.Status.PENDING,
            source=DicomServerFactory(),
            destination=DicomServerFactory(),
        )
        cls.study_task = TransferTaskFactory(
            patient_id=10001,
            study_uid="1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
            series_uids=[],
            pseudonym="",
            status=TransferTask.Status.PENDING,
            message="",
        )

    def test_transfer_study_to_server_succeeds(self):
        pass
        # # Arrange

        # # Act
        # transfer_dicoms(self.study_task.id)

        # # Assert
