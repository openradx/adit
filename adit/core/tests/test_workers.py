import pytest
from pytest_mock import MockerFixture

from adit.core.errors import RetriableDicomError

from ..models import DicomJob, DicomTask, QueuedTask
from ..processors import DicomTaskProcessor
from ..workers import DicomWorker
from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory
from .example_app.models import ExampleAppSettings, ExampleTransferTask


class ExampleProcessor(DicomTaskProcessor):
    app_name = "Example"
    dicom_task_class = ExampleTransferTask
    app_settings_class = ExampleAppSettings


@pytest.fixture(autouse=True)
def patch_dicom_processors(mocker: MockerFixture):
    model_label = f"{ExampleTransferTask._meta.app_label}.{ExampleTransferTask._meta.model_name}"
    mocker.patch.dict("adit.core.workers.dicom_processors", {f"{model_label}": ExampleProcessor})


@pytest.fixture
def dicom_worker(mocker: MockerFixture):
    worker = DicomWorker()
    worker._redis = mocker.MagicMock()
    return worker


@pytest.mark.django_db
def test_worker_with_task_that_succeeds(mocker: MockerFixture, dicom_worker: DicomWorker):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )
    queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

    def process_dicom_task(self, dicom_task):
        assert QueuedTask.objects.get(pk=queued_task.pk).locked
        return (DicomTask.Status.SUCCESS, "Success!", [])

    mocker.patch.object(ExampleProcessor, "process_dicom_task", process_dicom_task)

    dicom_worker.check_and_process_next_task()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.SUCCESS

    dicom_task.refresh_from_db()
    assert dicom_task.queued is None
    assert dicom_task.status == DicomTask.Status.SUCCESS
    assert dicom_task.message == "Success!"

    with pytest.raises(QueuedTask.DoesNotExist):
        QueuedTask.objects.get(pk=queued_task.pk)


@pytest.mark.django_db
def test_worker_with_task_that_fails(mocker: MockerFixture, dicom_worker: DicomWorker):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )
    queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

    def process_dicom_task(self, dicom_task):
        assert QueuedTask.objects.get(pk=queued_task.pk).locked
        return (DicomTask.Status.FAILURE, "Failure!", [])

    mocker.patch.object(ExampleProcessor, "process_dicom_task", process_dicom_task)

    dicom_worker.check_and_process_next_task()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.FAILURE

    dicom_task.refresh_from_db()
    assert dicom_task.queued is None
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "Failure!"

    with pytest.raises(QueuedTask.DoesNotExist):
        QueuedTask.objects.get(pk=queued_task.pk)


@pytest.mark.django_db
def test_worker_with_task_that_raises_non_retriable_error(
    mocker: MockerFixture, dicom_worker: DicomWorker
):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )
    queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

    def process_dicom_task(self, dicom_task):
        assert QueuedTask.objects.get(pk=queued_task.pk).locked
        raise Exception("Unexpected error!")

    mocker.patch.object(ExampleProcessor, "process_dicom_task", process_dicom_task)

    dicom_worker.check_and_process_next_task()

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.FAILURE

    dicom_task.refresh_from_db()
    assert dicom_task.queued is None
    assert dicom_task.status == DicomTask.Status.FAILURE
    assert dicom_task.message == "Unexpected error!"

    with pytest.raises(QueuedTask.DoesNotExist):
        QueuedTask.objects.get(pk=queued_task.pk)


@pytest.mark.django_db
def test_worker_with_task_that_raises_retriable_error(
    mocker: MockerFixture, dicom_worker: DicomWorker
):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )
    queued_task = QueuedTask.objects.create(content_object=dicom_task, priority=5)

    def process_dicom_task(self, dicom_task):
        assert QueuedTask.objects.get(pk=queued_task.pk).locked
        raise RetriableDicomError("Retriable error!")

    mocker.patch.object(ExampleProcessor, "process_dicom_task", process_dicom_task)

    dicom_worker.check_and_process_next_task()

    queued_task.refresh_from_db()
    assert not queued_task.locked

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.PENDING

    dicom_task.refresh_from_db()
    assert dicom_task.queued == queued_task
    assert dicom_task.status == DicomTask.Status.PENDING
    assert dicom_task.retries == 1
    assert QueuedTask.objects.get(pk=queued_task.pk)
