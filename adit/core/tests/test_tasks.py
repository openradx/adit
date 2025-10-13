import pytest
from adit_radis_shared.common.utils.testing_helpers import run_worker_once
from pytest_mock import MockerFixture

from adit.core.errors import RetriableDicomError
from adit.core.models import DicomJob, DicomTask
from adit.core.processors import DicomTaskProcessor
from adit.core.types import ProcessingResult
from adit.core.utils.model_utils import get_model_label

from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory
from .example_app.models import ExampleAppSettings, ExampleTransferTask


class ExampleProcessor(DicomTaskProcessor):
    app_name = "Example"
    dicom_task_class = ExampleTransferTask
    app_settings_class = ExampleAppSettings

    def process(self) -> ProcessingResult:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def patch_dicom_processors(mocker: MockerFixture):
    model_label = get_model_label(ExampleTransferTask)
    mocker.patch.dict(
        "adit.core.utils.task_utils.dicom_processors", {f"{model_label}": ExampleProcessor}
    )


@pytest.mark.django_db(transaction=True)
def test_process_dicom_task_that_succeeds(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )

    dicom_job.queue_pending_tasks()

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is not None

    def process(self):
        return {
            "status": DicomTask.Status.SUCCESS,
            "message": "Success!",
            "log": "",
        }

    mocker.patch.object(ExampleProcessor, "process", process)

    run_worker_once()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.SUCCESS

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is None
    assert dicom_task.status == DicomTask.Status.SUCCESS
    assert dicom_task.message == "Success!"
    assert dicom_task.attempts == 1


@pytest.mark.django_db(transaction=True)
def test_process_dicom_task_that_fails(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )

    dicom_job.queue_pending_tasks()

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is not None

    def process(self):
        return {
            "status": DicomTask.Status.FAILURE,
            "message": "Failure!",
            "log": "",
        }

    mocker.patch.object(ExampleProcessor, "process", process)

    run_worker_once()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.FAILURE

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is None
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "Failure!"
    assert dicom_task.attempts == 1


@pytest.mark.django_db(transaction=True)
def test_process_dicom_task_that_should_be_retried(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )

    dicom_job.queue_pending_tasks()

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is not None

    def process(self):
        raise RetriableDicomError("Retriable error!")

    mocker.patch.object(ExampleProcessor, "process", process)

    run_worker_once()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.PENDING

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is not None
    assert dicom_task.status == DicomTask.Status.PENDING
    assert dicom_task.message == "Task failed, but will be retried."
    assert dicom_task.attempts == 1


@pytest.mark.django_db(transaction=True)
def test_process_dicom_task_that_raises(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )

    dicom_job.queue_pending_tasks()

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is not None

    def process(self):
        raise Exception("Unexpected error!")

    mocker.patch.object(ExampleProcessor, "process", process)

    run_worker_once()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.FAILURE

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is None
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "Unexpected error!"
    assert dicom_task.attempts == 1
