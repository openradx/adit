from datetime import datetime
from unittest.mock import create_autospec, Mock, patch
import pytest
from celery import Task as CeleryTask
from celery.canvas import Signature
from celery.result import AsyncResult, ResultBase
from django.db.models.query import QuerySet
from ..tasks import ProcessDicomJob, ProcessDicomTask
from ..models import AppSettings, DicomJob, DicomTask


class TestProcessDicomJob:
    @pytest.mark.parametrize("urgent", [True, False])
    @patch("adit.core.tasks.chord", autospec=True)
    def test_run_succeeds(self, chord_mock, urgent):  # pylint: disable=too-many-locals
        # Arrange
        dicom_job_id = 9
        dicom_task_id = 8
        default_priority = 3
        urgent_priority = 7
        celery_task_id = "d2548e15-6597-4127-ab2f-98bae1bbf3f2"

        dicom_job_class_mock = Mock()
        dicom_job_mock = create_autospec(DicomJob)
        dicom_job_mock.id = dicom_job_id
        dicom_job_mock.urgent = urgent
        dicom_job_mock.status = DicomJob.Status.PENDING
        dicom_task_mock = create_autospec(DicomTask)
        dicom_task_mock.id = dicom_task_id
        dicom_job_mock.tasks = create_autospec(QuerySet)
        dicom_job_mock.tasks.filter.return_value = [dicom_task_mock]
        dicom_job_class_mock.objects.get.return_value = dicom_job_mock

        process_dicom_job = ProcessDicomJob()
        process_dicom_job.dicom_job_class = dicom_job_class_mock
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
        process_dicom_job.handle_failed_dicom_job.s.return_value = (
            handle_failed_dicom_task_sig_mock
        )

        async_result_mock = create_autospec(AsyncResult)
        async_result_mock.id = celery_task_id

        chain_result_mock = create_autospec(ResultBase)
        chain_result_mock.parent.results = [async_result_mock]
        chord_mock.return_value.return_value = chain_result_mock

        # Act
        process_dicom_job.run(dicom_job_id)

        # Assert
        dicom_job_class_mock.objects.get.assert_called_once_with(id=dicom_job_id)
        dicom_job_mock.tasks.filter.assert_called_once_with(
            status=DicomTask.Status.PENDING
        )
        process_dicom_job.process_dicom_task.s.assert_called_once_with(dicom_task_id)

        if urgent:
            process_dicom_job.process_dicom_task.s.return_value.set.assert_called_once_with(
                priority=urgent_priority
            )
        else:
            process_dicom_job.process_dicom_task.s.return_value.set.assert_called_once_with(
                priority=default_priority
            )

        chord_mock.assert_called_once_with([process_dicom_task_sig_mock])

        process_dicom_job.handle_finished_dicom_job.s.assert_called_once_with(
            dicom_job_id
        )
        process_dicom_job.handle_failed_dicom_job.s.assert_called_once_with(
            job_id=dicom_job_id
        )
        process_dicom_job.handle_finished_dicom_job.s.return_value.on_error.assert_called_once_with(
            handle_failed_dicom_task_sig_mock
        )

        chord_mock.return_value.assert_called_once_with(
            handle_finished_dicom_task_sig_mock
        )

        assert dicom_task_mock.celery_task_id == celery_task_id
        dicom_task_mock.save.assert_called_once()


class TestProcessDicomTask:
    @patch("adit.core.tasks.Scheduler", autospec=True)
    def test_run_urgent_task_succeeds(self, scheduler_mock):
        # Arrange
        dicom_task_id = 8

        dicom_task_class_mock = Mock()
        dicom_task_mock = create_autospec(DicomTask)
        dicom_task_mock.id = dicom_task_id
        dicom_task_mock.status = DicomTask.Status.PENDING
        dicom_job_mock = create_autospec(DicomJob)
        dicom_job_mock.status = DicomJob.Status.PENDING
        dicom_job_mock.urgent = True
        dicom_task_mock.job = dicom_job_mock
        dicom_task_class_mock.objects.get.return_value = dicom_task_mock

        app_settings_class_mock = Mock()
        app_settings_mock = create_autospec(AppSettings)
        app_settings_mock.suspended = False
        app_settings_class_mock.get.return_value = app_settings_mock

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = dicom_task_class_mock
        process_dicom_task.app_settings_class = app_settings_class_mock

        with patch.object(
            ProcessDicomTask, "handle_dicom_task"
        ) as handle_dicom_task_mock:
            handle_dicom_task_mock.return_value = DicomTask.Status.SUCCESS

            # Act
            result = process_dicom_task.run(dicom_task_id)

        # Assert
        dicom_task_class_mock.objects.get.assert_called_once_with(id=dicom_task_id)
        assert not scheduler_mock.must_be_scheduled.called
        assert dicom_job_mock.status == DicomJob.Status.IN_PROGRESS
        dicom_job_mock.save.assert_called_once()
        assert isinstance(dicom_job_mock.start, datetime)
        handle_dicom_task_mock.assert_called_once_with(dicom_task_mock)
        assert result == DicomTask.Status.SUCCESS

    @pytest.mark.skip  # TODO
    def test_canceled_task_returns_canceled(self):
        pass

    @pytest.mark.skip  # TODO
    def test_non_urgent_task_in_time_slot_succeeds(self):
        pass

    @pytest.mark.skip  # TODO
    def test_non_urgent_task_outside_time_slot_is_rescheduled(self):
        pass

    @pytest.mark.skip  # TODO
    def test_when_suspended_gets_rescheduled(self):
        pass


class TestHandleFinishedDicomJob:
    @pytest.mark.skip  # TODO
    def test_handles_finshed_job_successfully(self):
        pass


class TestHandleFailedDicomJob:
    @pytest.mark.skip  # TODO
    def test_handles_failed_job_successfully(self):
        pass
