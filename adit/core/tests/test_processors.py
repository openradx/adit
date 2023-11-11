import pytest
from pytest_mock import MockerFixture

from ..factories import DicomServerFactory
from ..models import DicomJob, DicomTask, QueuedTask
from ..processors import ProcessDicomTask
from .conftest import ExampleModels


class TestProcessDicomTask:
    @pytest.mark.parametrize("urgent", [True, False])
    def test_process_dicom_task_succeeds(
        self, mocker: MockerFixture, urgent, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
            urgent=urgent,
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            source=DicomServerFactory(),
            job=dicom_job,
        )
        queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        mocker.patch.object(
            ProcessDicomTask,
            "handle_dicom_task",
            lambda self, dicom_task: (DicomTask.Status.SUCCESS, "Success!", []),
        )

        # Act
        process_dicom_task.run(queued_task)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.SUCCESS

        dicom_task.refresh_from_db()
        assert dicom_task.status == DicomTask.Status.SUCCESS
        assert dicom_task.message == "Success!"

    def test_dicom_job_fails_when_dicom_task_fails(
        self, mocker: MockerFixture, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            source=DicomServerFactory(),
            job=dicom_job,
        )
        queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        mocker.patch.object(
            ProcessDicomTask,
            "handle_dicom_task",
            lambda self, dicom_task: (DicomTask.Status.FAILURE, "Failure!", []),
        )

        # Act
        process_dicom_task.run(queued_task)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.FAILURE

        dicom_task.refresh_from_db()
        assert dicom_task.status == DicomTask.Status.FAILURE
        assert dicom_task.message == "Failure!"

    def test_dicom_job_fails_when_dicom_task_raises(
        self, mocker: MockerFixture, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.PENDING,
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            source=DicomServerFactory(),
            job=dicom_job,
        )
        queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        def handle_dicom_task(self, dicom_task):
            raise Exception("Unexpected error!")

        mocker.patch.object(ProcessDicomTask, "handle_dicom_task", handle_dicom_task)

        # Act
        process_dicom_task.run(queued_task)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.FAILURE

        dicom_task.refresh_from_db()
        assert dicom_task.status == DicomTask.Status.FAILURE
        assert dicom_task.message == "Unexpected error!"

    def test_dicom_job_canceled_when_dicom_task_canceled(
        self, mocker: MockerFixture, example_models: ExampleModels
    ):
        # Arrange
        dicom_job = example_models.dicom_job_factory_class.create(
            status=DicomJob.Status.CANCELING,
        )
        dicom_task = example_models.dicom_task_factory_class.create(
            status=DicomTask.Status.PENDING,
            source=DicomServerFactory(),
            job=dicom_job,
        )
        queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

        process_dicom_task = ProcessDicomTask()
        process_dicom_task.dicom_task_class = example_models.dicom_task_class
        process_dicom_task.app_settings_class = example_models.app_settings_class

        def handle_dicom_task(self, dicom_task):
            raise Exception("Should never raise!")

        mocker.patch.object(ProcessDicomTask, "handle_dicom_task", handle_dicom_task)

        # Act
        process_dicom_task.run(queued_task)

        # Assert
        dicom_job.refresh_from_db()
        assert dicom_job.status == DicomJob.Status.CANCELED

        dicom_task.refresh_from_db()
        assert dicom_task.status == DicomTask.Status.CANCELED
        assert dicom_task.message == "Task was canceled."

    @pytest.mark.skip  # TODO
    def test_when_suspended_gets_rescheduled(self):
        pass
