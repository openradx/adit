from unittest.mock import patch, Mock, create_autospec
import pytest
from django.conf import settings
from adit.core.models import TransferJob, TransferTask
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.factories import DicomServerFactory
from adit.core.utils.scheduler import Scheduler
from ..factories import BatchTransferJobFactory, BatchTransferTaskFactory
from ..models import BatchTransferJob, BatchTransferTask
from ..tasks import batch_transfer, transfer_dicoms


@pytest.mark.django_db
@patch("adit.batch_transfer.tasks.on_job_failed")
@patch("adit.batch_transfer.tasks.on_job_finished")
@patch("adit.batch_transfer.tasks.chord")
@patch("adit.batch_transfer.tasks.transfer_dicoms")
def test_batch_transfer_finished_with_success(
    transfer_dicoms_mock,
    chord_mock,
    on_job_finished_mock,
    on_job_failed_mock,
):
    # Arrange
    job = BatchTransferJobFactory(
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        status=TransferJob.Status.PENDING,
    )
    transfer_task = BatchTransferTaskFactory(
        job=job, status=BatchTransferTask.Status.PENDING
    )

    transfer_dicoms_s_mock = Mock()
    transfer_dicoms_mock.s.return_value.set.return_value = transfer_dicoms_s_mock

    header_mock = Mock()
    chord_mock.return_value = header_mock

    on_job_finished_s_mock = Mock()
    on_job_finished_mock.s.return_value = on_job_finished_s_mock
    on_job_finished_on_error_mock = Mock()
    on_job_finished_s_mock.on_error.return_value = on_job_finished_on_error_mock

    on_job_failed_mock_s_mock = Mock()
    on_job_failed_mock.s.return_value = on_job_failed_mock_s_mock

    priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY

    # Act
    batch_transfer(job.id)

    # Assert
    transfer_dicoms_mock.s.assert_called_once_with(transfer_task.id)
    transfer_dicoms_mock.s.return_value.set.assert_called_once_with(priority=priority)
    chord_mock.assert_called_once_with([transfer_dicoms_s_mock])
    on_job_finished_mock.s.assert_called_once_with(job.id)
    on_job_failed_mock.s.assert_called_once_with(job_id=job.id)
    header_mock.assert_called_once_with(on_job_finished_on_error_mock)


@pytest.mark.django_db
@patch.object(Scheduler, "must_be_scheduled", return_value=False)
@patch("adit.batch_transfer.tasks.TransferUtil.start_transfer")
def test_transfer_task_without_study_fails(
    start_transfer_mock,
    must_be_scheduled_mock,
):
    # Arrange
    job = BatchTransferJobFactory(status=TransferJob.Status.PENDING, urgent=False)
    transfer_task = BatchTransferTaskFactory(
        job=job, status=BatchTransferTask.Status.PENDING
    )

    patient = {
        "PatientID": "1234",
        "PatientName": "John^Doe",
        "PatientBirthDate": "19801230",
    }
    connector = create_autospec(DicomConnector)
    connector.find_patients.return_value = [patient]
    connector.find_studies.return_value = []

    start_transfer_mock.return_value = TransferTask.Status.SUCCESS

    with patch.object(BatchTransferJob, "source") as source_mock:
        source_mock.dicomserver.create_connector.return_value = connector

        # Act
        result = transfer_dicoms(transfer_task.id)

        # Assert
        transfer_task.refresh_from_db()
        assert result == BatchTransferTask.Status.WARNING
        assert result == transfer_task.status
        assert transfer_task.message == "No studies found to transfer."
        source_mock.dicomserver.create_connector.assert_called_once()
        must_be_scheduled_mock.assert_called_once()
