from unittest.mock import create_autospec, patch

import pytest
from celery import Task as CeleryTask
from celery.canvas import Signature
from celery.result import AsyncResult

from ..factories import DicomServerFactory
from ..models import DicomJob, DicomTask
from ..tasks import ProcessDicomJob, ProcessDicomTask
from .conftest import ExampleModels


class TestProcessDicomJob:
    @pytest.mark.parametrize("urgent", [True, False])
    def test_run_succeeds(self, urgent, example_models: ExampleModels):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
            source=DicomServerFactory(),
            urgent=urgent,
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            job=dicom_job,
        )

        default_priority = 2
        urgent_priority = 4
        celery_task_id = "d2548e15-6597-4127-ab2f-98bae1bbf3f2"

        process_dicom_job = ProcessDicomJob()
        process_dicom_job.dicom_job_class = example_models.dicom_job_class
        process_dicom_job.default_priority = default_priority
        process_dicom_job.urgent_priority = urgent_priority

        process_dicom_task = create_autospec(CeleryTask)
        process_dicom_job.process_dicom_task = process_dicom_task

        signature_mock = create_autospec(Signature)
        process_dicom_task.s.return_value = signature_mock
        signature_mock.set.return_value = signature_mock

        async_result_mock = create_autospec(AsyncResult)
        async_result_mock.id = celery_task_id
        signature_mock.delay.return_value = async_result_mock

        # Act
        process_dicom_job.run(dicom_job.id)

        # Assert
        process_dicom_task.s.assert_called_once_with(dicom_task.id)

        if urgent:
            signature_mock.set.assert_called_once_with(priority=urgent_priority)
        else:
            signature_mock.set.assert_called_once_with(priority=default_priority)

        signature_mock.delay.assert_called_once()

        dicom_task.refresh_from_db()
        assert dicom_task.celery_task_id == celery_task_id


class TestProcessDicomTask:
    @pytest.mark.parametrize("urgent", [True, False])
    @patch("adit.core.tasks.Scheduler", autospec=True)
    def test_process_dicom_task_succeeds(
        self, scheduler_mock, urgent, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
            source=DicomServerFactory(),
            urgent=urgent,
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            job=dicom_job,
        )

        scheduler_mock.return_value.must_be_scheduled.return_value = False

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        def handle_dicom_task(self, dicom_task):
            return (DicomTask.Status.SUCCESS, "Success!")

        with patch.object(ProcessDicomTask, "handle_dicom_task", handle_dicom_task):
            # Act
            result = process_dicom_task.run(dicom_task.id)

        # Assert
        if urgent:
            scheduler_mock.return_value.must_be_scheduled.assert_not_called()
        else:
            scheduler_mock.return_value.must_be_scheduled.assert_called_once()

        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.SUCCESS

        dicom_task.refresh_from_db()
        assert result == DicomTask.Status.SUCCESS
        assert dicom_task.status == result
        assert dicom_task.message == "Success!"

    @patch("adit.core.tasks.Scheduler", autospec=True)
    def test_dicom_job_fails_when_dicom_task_fails(
        self, scheduler_mock, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
            source=DicomServerFactory(),
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            job=dicom_job,
        )

        scheduler_mock.return_value.must_be_scheduled.return_value = False

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        def handle_dicom_task(self, dicom_task):
            return (DicomTask.Status.FAILURE, "Failure!")

        with patch.object(ProcessDicomTask, "handle_dicom_task", handle_dicom_task):
            # Act
            result = process_dicom_task.run(dicom_task.id)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.FAILURE

        dicom_task.refresh_from_db()
        assert result == DicomTask.Status.FAILURE
        assert dicom_task.status == result
        assert dicom_task.message == "Failure!"

    @patch("adit.core.tasks.Scheduler", autospec=True)
    def test_dicom_job_fails_when_dicom_task_raises(
        self, scheduler_mock, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
            source=DicomServerFactory(),
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            job=dicom_job,
        )

        scheduler_mock.return_value.must_be_scheduled.return_value = False

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        def handle_dicom_task(self, dicom_task):
            raise Exception("Unexpected error!")

        with patch.object(ProcessDicomTask, "handle_dicom_task", handle_dicom_task):
            # Act
            result = process_dicom_task.run(dicom_task.id)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.FAILURE

        dicom_task.refresh_from_db()
        assert result == DicomTask.Status.FAILURE
        assert dicom_task.status == result
        assert dicom_task.message == "Unexpected error!"

    @patch("adit.core.tasks.Scheduler", autospec=True)
    def test_dicom_job_canceled_when_dicom_task_canceled(
        self, scheduler_mock, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.CANCELING,
            source=DicomServerFactory(),
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            job=dicom_job,
        )

        scheduler_mock.return_value.must_be_scheduled.return_value = False

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        def handle_dicom_task(self, dicom_task):
            raise Exception("Should never raise!")

        with patch.object(ProcessDicomTask, "handle_dicom_task", handle_dicom_task):
            # Act
            result = process_dicom_task.run(dicom_task.id)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.CANCELED

        dicom_task.refresh_from_db()
        assert result == DicomTask.Status.CANCELED
        assert dicom_task.status == result
        assert dicom_task.message == "Task was canceled."

    @pytest.mark.skip  # TODO
    def test_non_urgent_task_in_time_slot_succeeds(self):
        pass

    @pytest.mark.skip  # TODO
    def test_non_urgent_task_outside_time_slot_is_rescheduled(self):
        pass

    @pytest.mark.skip  # TODO
    def test_when_suspended_gets_rescheduled(self):
        pass
