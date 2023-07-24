from datetime import datetime
from unittest.mock import Mock, create_autospec, patch

import pytest
from celery import Task as CeleryTask
from celery.canvas import Signature
from celery.result import AsyncResult, ResultBase

from adit.accounts.factories import UserFactory

from ..models import AppSettings, DicomJob, DicomTask
from ..tasks import ProcessDicomJob, ProcessDicomTask
from .conftest import (
    DummyTransferJob,
    DummyTransferJobFactory,
    DummyTransferTask,
    DummyTransferTaskFactory,
)


class TestProcessDicomJob:
    @pytest.mark.django_db
    @pytest.mark.parametrize("is_staff", [True])
    @pytest.mark.parametrize("urgent", [True])
    @patch("adit.core.tasks.chord", autospec=True)
    def test_process_dicom_job_succeeds(self, chord_mock, is_staff, urgent):
        # Arrange
        user = UserFactory(is_staff=is_staff)
        job = DummyTransferJobFactory(
            owner=user, status=DummyTransferJob.Status.PENDING, urgent=urgent
        )
        task = DummyTransferTaskFactory(job=job, status=DummyTransferTask.Status.PENDING)

        default_priority = 2
        urgent_priority = 5

        process_dicom_job = ProcessDicomJob()
        process_dicom_job.dicom_job_class = DummyTransferJob
        process_dicom_job.default_priority = default_priority
        process_dicom_job.urgent_priority = urgent_priority
        process_dicom_job.process_dicom_task = create_autospec(CeleryTask)
        process_dicom_job.handle_finished_dicom_job = create_autospec(CeleryTask)
        process_dicom_job.handle_failed_dicom_job = create_autospec(CeleryTask)

        process_dicom_task_sig_mock = create_autospec(Signature)
        process_dicom_job.process_dicom_task.s.return_value.set.return_value = (
            process_dicom_task_sig_mock
        )

        handle_finished_dicom_task_sig_mock = create_autospec(Signature)
        process_dicom_job.handle_finished_dicom_job.s.return_value.on_error.return_value = (
            handle_finished_dicom_task_sig_mock
        )

        handle_failed_dicom_task_sig_mock = create_autospec(Signature)
        process_dicom_job.handle_failed_dicom_job.s.return_value = handle_failed_dicom_task_sig_mock

        async_result_mock = create_autospec(AsyncResult)
        celery_task_id = "d2548e15-6597-4127-ab2f-98bae1bbf3f2"
        async_result_mock.id = celery_task_id

        chain_result_mock = create_autospec(ResultBase)
        chain_result_mock.parent.results = [async_result_mock]
        chord_mock.return_value.return_value = chain_result_mock

        # Act
        process_dicom_job.run(job.id)

        # Assert
        process_dicom_job.process_dicom_task.s.assert_called_once_with(task.id)

        actual_priority = default_priority if not urgent else urgent_priority
        if is_staff:
            actual_priority += 1

        process_dicom_job.process_dicom_task.s.return_value.set.assert_called_once_with(
            priority=actual_priority
        )

        chord_mock.assert_called_once_with([process_dicom_task_sig_mock])

        process_dicom_job.handle_finished_dicom_job.s.assert_called_once_with(job.id)
        process_dicom_job.handle_failed_dicom_job.s.assert_called_once_with(job_id=job.id)
        process_dicom_job.handle_finished_dicom_job.s.return_value.on_error.assert_called_once_with(
            handle_failed_dicom_task_sig_mock
        )

        chord_mock.return_value.assert_called_once_with(handle_finished_dicom_task_sig_mock)

        task.refresh_from_db()
        assert task.celery_task_id == celery_task_id

        user.delete()
        job.delete()
        task.delete()
