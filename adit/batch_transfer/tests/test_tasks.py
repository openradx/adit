from unittest.mock import patch, Mock
import pytest
from django.conf import settings
from adit.core.models import TransferJob, TransferTask
from adit.core.factories import DicomServerFactory
from ..factories import BatchTransferJobFactory, BatchTransferTaskFactory
from ..models import BatchTransferJob, BatchTransferTask
from ..tasks import process_transfer_job, process_transfer_task


@pytest.mark.django_db
@pytest.mark.parametrize("urgent", [True, False])
@patch("adit.batch_transfer.tasks.on_job_failed.s", autospec=True)
@patch("adit.batch_transfer.tasks.on_job_finished.s", autospec=True)
@patch("adit.batch_transfer.tasks.process_transfer_task.s", autospec=True)
@patch("adit.batch_transfer.tasks.chord", autospec=True)
def test_process_transfer_job_succeeds(
    mock_chord,
    mock_process_transfer_task_s,
    mock_on_job_finished_s,
    mock_on_job_failed_s,
    urgent,
):
    # Arrange
    job = BatchTransferJobFactory(
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        status=TransferJob.Status.PENDING,
        urgent=urgent,
    )
    transfer_task = BatchTransferTaskFactory(
        job=job, status=BatchTransferTask.Status.PENDING
    )

    mock_process_transfer_task_signature = Mock()
    mock_process_transfer_task_s.return_value.set.return_value = (
        mock_process_transfer_task_signature
    )

    mock_header = Mock()
    mock_chord.return_value = mock_header

    mock_on_job_failed_signature = Mock()
    mock_on_job_failed_s.return_value = mock_on_job_failed_signature

    mock_on_job_finished_signature = Mock()
    mock_on_job_finished_s.return_value.on_error.return_value = (
        mock_on_job_finished_signature
    )

    # Act
    process_transfer_job(job.id)

    # Assert
    if urgent:
        priority = settings.BATCH_TRANSFER_URGENT_PRIORITY
    else:
        priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY

    mock_process_transfer_task_s.assert_called_once_with(transfer_task.id)
    mock_process_transfer_task_s.return_value.set.assert_called_once_with(
        priority=priority
    )
    mock_chord.assert_called_once_with([mock_process_transfer_task_signature])
    mock_on_job_finished_s.assert_called_once_with(job.id)
    mock_on_job_finished_s.return_value.on_error.assert_called_once_with(
        mock_on_job_failed_signature
    )
    mock_on_job_failed_s.assert_called_once_with(job_id=job.id)
    mock_header.assert_called_once_with(mock_on_job_finished_signature)


@pytest.mark.django_db
@patch("adit.batch_transfer.tasks.execute_transfer", autospec=True)
def test_transfer_task_without_study_fails(
    execute_transfer_mock,
):
    # Arrange
    transfer_job = BatchTransferJobFactory(
        urgent=True, status=BatchTransferJob.Status.IN_PROGRESS
    )
    transfer_task = BatchTransferTaskFactory(
        job=transfer_job, status=BatchTransferTask.Status.PENDING
    )
    execute_transfer_mock.return_value = TransferTask.Status.SUCCESS

    # Act
    status = process_transfer_task(  # pylint: disable=no-value-for-parameter
        transfer_task.id
    )

    # Assert
    execute_transfer_mock.assert_called_once_with(transfer_task)
    assert status == TransferTask.Status.SUCCESS
