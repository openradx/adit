from unittest.mock import patch, Mock, create_autospec
import pytest
from django.conf import settings
from adit.core.models import TransferJob, TransferTask
from adit.core.factories import DicomServerFactory
from adit.core.utils.scheduler import Scheduler
from ..factories import BatchTransferJobFactory, BatchTransferTaskFactory
from ..models import BatchTransferTask
from ..tasks import process_transfer_job, process_transfer_task


@pytest.mark.django_db
@pytest.mark.parametrize("urgent", [True, False])
@patch("adit.batch_transfer.tasks.on_job_failed", autospec=True)
@patch("adit.batch_transfer.tasks.on_job_finished", autospec=True)
@patch("adit.batch_transfer.tasks.chord", autospec=True)
@patch("adit.batch_transfer.tasks.process_transfer_task", autospec=True)
def test_process_transfer_job_succeeds(
    process_transfer_task_mock,
    chord_mock,
    on_job_finished_mock,
    on_job_failed_mock,
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

    process_transfer_task_s_mock = Mock()
    process_transfer_task_mock.s.return_value.set.return_value = (
        process_transfer_task_s_mock
    )

    header_mock = Mock()
    chord_mock.return_value = header_mock

    on_job_finished_s_mock = Mock()
    on_job_finished_mock.s.return_value = on_job_finished_s_mock
    on_job_finished_on_error_mock = Mock()
    on_job_finished_s_mock.on_error.return_value = on_job_finished_on_error_mock

    on_job_failed_mock_s_mock = Mock()
    on_job_failed_mock.s.return_value = on_job_failed_mock_s_mock

    # Act
    process_transfer_job(job.id)

    # Assert
    if urgent:
        priority = settings.BATCH_TRANSFER_URGENT_PRIORITY
    else:
        priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY

    process_transfer_task_mock.s.assert_called_once_with(transfer_task.id)
    process_transfer_task_mock.s.return_value.set.assert_called_once_with(
        priority=priority
    )
    chord_mock.assert_called_once_with([process_transfer_task_s_mock])
    on_job_finished_mock.s.assert_called_once_with(job.id)
    on_job_failed_mock.s.assert_called_once_with(job_id=job.id)
    header_mock.assert_called_once_with(on_job_finished_on_error_mock)


@pytest.mark.django_db
@patch("adit.batch_transfer.tasks.prepare_dicom_task", autospec=True)
@patch("adit.batch_transfer.tasks.execute_transfer", autospec=True)
def test_transfer_task_without_study_fails(
    execute_transfer_mock,
    prepare_dicom_task_mock,
):
    # Arrange
    transfer_task = BatchTransferTaskFactory(status=BatchTransferTask.Status.PENDING)
    execute_transfer_mock.return_value = TransferTask.Status.SUCCESS

    # Act
    status = process_transfer_task(  # pylint: disable=no-value-for-parameter
        transfer_task.id
    )

    # Assert
    prepare_dicom_task_mock.assert_called_once_with(transfer_task)
    execute_transfer_mock.assert_called_once_with(transfer_task)
    assert status == TransferTask.Status.SUCCESS
