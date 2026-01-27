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


@pytest.mark.django_db(transaction=True)
def test_process_dicom_task_transitions_to_failure_after_max_retries(mocker: MockerFixture):
    """Test that a task correctly transitions to FAILURE after exhausting all retries.

    This test verifies the fix for the off-by-one error where tasks would stay in
    PENDING status with "Task failed, but will be retried" even after exhausting
    all retry attempts.

    With DICOM_TASK_MAX_ATTEMPTS=3 (default), the task should transition to FAILURE
    after the third attempt. The fixed condition `attempts + 1 < max_attempts`
    on the 3rd attempt gives `2 + 1 < 3` = False, so it should transition to FAILURE.

    We simulate the final attempt by setting the queued job's attempts to max_attempts-1.
    """
    from django.conf import settings
    from procrastinate.contrib.django.models import ProcrastinateJob

    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )

    dicom_job.queue_pending_tasks()

    dicom_task.refresh_from_db()
    assert dicom_task.queued_job is not None

    error_message = "Connection refused by server"

    def process(self):
        raise RetriableDicomError(error_message)

    mocker.patch.object(ExampleProcessor, "process", process)

    # Set the job's attempts to max_attempts-1 to simulate this being the final attempt
    # Procrastinate's attempts is 0-indexed (counts previous attempts), so:
    # - attempts=0: first attempt (attempts + 1 = 1)
    # - attempts=1: second attempt (attempts + 1 = 2)
    # - attempts=2: third/final attempt (attempts + 1 = 3)
    # With DICOM_TASK_MAX_ATTEMPTS=3, the check is: 2 + 1 < 3 = False → FAILURE
    final_attempt = settings.DICOM_TASK_MAX_ATTEMPTS - 1
    ProcrastinateJob.objects.filter(id=dicom_task.queued_job_id).update(attempts=final_attempt)

    run_worker_once()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.FAILURE

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.FAILURE
    # On final attempt, message should be the actual error, not "will be retried"
    assert dicom_task.message == error_message
    assert "Task failed, but will be retried" not in dicom_task.message
