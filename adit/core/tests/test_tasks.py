from concurrent import futures
from types import SimpleNamespace
from typing import cast

import pytest
from adit_radis_shared.common.utils.testing_helpers import run_worker_once
from procrastinate import JobContext
from pytest_mock import MockerFixture

from adit.core import tasks as tasks_module
from adit.core.errors import DicomError, RetriableDicomError
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


# ---------------------------------------------------------------------------
# Direct _run_dicom_task tests
#
# These exercise the task-processing layer (including the pglock.advisory
# distributed-lock + post_process path) without spawning a real pebble
# subprocess. The pebble process/thread helpers are stubbed so the processor's
# process() runs in-process and we control the future result, cancellation and
# timeouts deterministically.
# ---------------------------------------------------------------------------


class _FakeFuture:
    def __init__(self, result=None, exc: Exception | None = None):
        self._result = result
        self._exc = exc

    def done(self) -> bool:
        return True

    def result(self):
        if self._exc is not None:
            raise self._exc
        return self._result


def _install_pebble_stubs(
    mocker: MockerFixture,
    *,
    future: _FakeFuture,
) -> None:
    """Replace pebble's process/thread decorators so no real subprocess/thread runs.

    `concurrent.process(...)` returns a decorator; the decorated callable returns
    our fake future. `concurrent.thread()` returns a decorator whose callable is a
    no-op (the monitor loop is irrelevant when the future is already done).
    """

    def fake_process(*p_args, **p_kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return future

            return wrapper

        return decorator

    def fake_thread(*t_args, **t_kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return None

            return wrapper

        return decorator

    mocker.patch.object(tasks_module.concurrent, "process", side_effect=fake_process)
    mocker.patch.object(tasks_module.concurrent, "thread", side_effect=fake_thread)


def _make_context(attempts: int = 0) -> JobContext:
    job = SimpleNamespace(attempts=attempts)
    # _run_dicom_task only reads context.job.attempts and context.should_abort();
    # a SimpleNamespace duck-types those without building a full JobContext.
    return cast(JobContext, SimpleNamespace(job=job, should_abort=lambda: False))


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_success_sets_job_in_progress_then_finishes(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    result: ProcessingResult = {
        "status": DicomTask.Status.SUCCESS,
        "message": "All good",
        "log": "some log",
    }
    _install_pebble_stubs(mocker, future=_FakeFuture(result=result))

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    dicom_job.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.SUCCESS
    assert dicom_task.message == "All good"
    assert dicom_task.log == "some log"
    assert dicom_task.attempts == 1
    assert dicom_task.end is not None
    # Job started (PENDING -> IN_PROGRESS happened) and then post_process finished it
    assert dicom_job.start is not None
    assert dicom_job.status == DicomJob.Status.SUCCESS


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_handles_cancellation(mocker: MockerFixture):
    # In the real flow a cancel request first moves the job to CANCELING; the
    # task then surfaces a CancelledError. post_process resolves CANCELING -> CANCELED.
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.CANCELING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    _install_pebble_stubs(
        mocker, future=_FakeFuture(exc=futures.CancelledError())
    )

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    dicom_job.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.CANCELED
    assert dicom_task.message == "Task was canceled."
    assert dicom_job.status == DicomJob.Status.CANCELED


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_handles_timeout(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    _install_pebble_stubs(mocker, future=_FakeFuture(exc=futures.TimeoutError()))

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "Task was aborted due to timeout."


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_retriable_error_below_max_marks_pending_and_reraises(
    mocker: MockerFixture,
):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    _install_pebble_stubs(
        mocker, future=_FakeFuture(exc=RetriableDicomError("transient"))
    )

    # attempts=0 -> 0 + 1 < 3 -> should be retried
    with pytest.raises(RetriableDicomError, match="transient"):
        tasks_module._run_dicom_task(_make_context(attempts=0), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.PENDING
    assert dicom_task.message == "Task failed, but will be retried."
    assert "transient" in dicom_task.log


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_retriable_error_on_final_attempt_marks_failure(
    mocker: MockerFixture,
):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    _install_pebble_stubs(
        mocker, future=_FakeFuture(exc=RetriableDicomError("permanent"))
    )

    # attempts=2 -> 2 + 1 < 3 is False -> FAILURE (with default DICOM_TASK_MAX_ATTEMPTS=3)
    with pytest.raises(RetriableDicomError, match="permanent"):
        tasks_module._run_dicom_task(_make_context(attempts=2), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "permanent"


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_unexpected_error_marks_failure_with_traceback(
    mocker: MockerFixture,
):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    _install_pebble_stubs(
        mocker, future=_FakeFuture(exc=ValueError("kaboom"))
    )

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "kaboom"
    # Traceback appended to the log
    assert "Traceback" in dicom_task.log


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_non_retriable_dicom_error_marks_failure(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    _install_pebble_stubs(
        mocker, future=_FakeFuture(exc=DicomError("bad config"))
    )

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "bad config"


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_accepts_in_progress_task_on_retry(mocker: MockerFixture):
    """A retried task may arrive IN_PROGRESS (worker killed before finally ran)."""
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.IN_PROGRESS, job=dicom_job
    )
    model_label = get_model_label(ExampleTransferTask)

    result: ProcessingResult = {
        "status": DicomTask.Status.SUCCESS,
        "message": "recovered",
        "log": "",
    }
    _install_pebble_stubs(mocker, future=_FakeFuture(result=result))

    # Should not raise the PENDING/IN_PROGRESS assertion
    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.SUCCESS
    assert dicom_task.message == "recovered"


@pytest.mark.django_db
def test_check_disk_space_warns_when_over_limit(mocker: MockerFixture):
    from adit.core.factories import DicomFolderFactory

    folder = DicomFolderFactory.create()
    folder.warn_size = 1  # 1 GB
    folder.quota = 10
    folder.save()

    # du returns size in MB; 5000 MB ~= 4.88 GB > 1 GB warn threshold
    mocker.patch.object(
        tasks_module.subprocess, "check_output", return_value=b"5000\t/some/path\n"
    )
    mail_mock = mocker.patch.object(tasks_module, "send_mail_to_admins")

    tasks_module.check_disk_space()

    mail_mock.assert_called_once()
    assert "low disk space" in mail_mock.call_args.args[0].lower()


@pytest.mark.django_db
def test_check_disk_space_no_warning_when_under_limit(mocker: MockerFixture):
    from adit.core.factories import DicomFolderFactory

    folder = DicomFolderFactory.create()
    folder.warn_size = 100  # 100 GB
    folder.quota = 200
    folder.save()

    # 5000 MB ~= 4.88 GB < 100 GB threshold
    mocker.patch.object(
        tasks_module.subprocess, "check_output", return_value=b"5000\t/some/path\n"
    )
    mail_mock = mocker.patch.object(tasks_module, "send_mail_to_admins")

    tasks_module.check_disk_space()

    mail_mock.assert_not_called()
