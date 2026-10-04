from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob
from pydicom import Dataset
from pydicom.data import get_testdata_file
from pydicom.uid import JPEGLSLossless, MRImageStorage
from pynetdicom.presentation import PresentationContext
from pytest_mock import MockerFixture

from adit.core.errors import DicomError
from adit.core.models import DicomTask
from adit.core.utils.dicom_utils import read_dataset, write_dataset
from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.recovery import dicom_task_models
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.factories import (
    RouterBatchFactory,
    RouterJobFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterTask, RoutingRule
from adit.router.processors import RouterTaskProcessor
from adit.router.utils import spool


@pytest.fixture
def spool_root(tmp_path: Path, settings) -> Path:
    settings.ROUTER_SPOOL_PATH = str(tmp_path)
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


class _Uploads:
    """Stands in for DicomOperator and keeps what upload_images would have sent."""

    def __init__(self, mocker: MockerFixture):
        self.datasets: list[Dataset] = []
        self.store_contexts: list[PresentationContext] | None = None

        def make_operator(server, store_contexts=None, **kwargs):
            self.store_contexts = store_contexts
            operator = mocker.MagicMock()
            operator.upload_images.side_effect = lambda folder: self.datasets.extend(
                read_dataset(path) for path in sorted(Path(folder).iterdir())
            )
            return operator

        mocker.patch("adit.router.processors.DicomOperator", side_effect=make_operator)


def _ct_images() -> list[Dataset]:
    return [ds for ds in load_sample_dicoms("1004") if ds.Modality == "CT"]


def _task(spool_root: Path, datasets: list[Dataset], rule: RoutingRule) -> RouterTask:
    batch = RouterBatchFactory.create(study_instance_uid=str(datasets[0].StudyInstanceUID))
    path = spool.batch_dir(spool_root, batch.sender_id, batch.batch_id)
    path.mkdir(parents=True)
    for ds in datasets:
        write_dataset(ds, path / f"{ds.SOPInstanceUID}.dcm")
    job = RouterJobFactory.create(
        rule=rule,
        batch=batch,
        trial_protocol_id=rule.trial_protocol_id,
        trial_protocol_name="",
    )
    patient_id = str(datasets[0].PatientID)
    return RouterTaskFactory.create(
        job=job,
        source=batch.sender.server,
        destination=rule.destination,
        patient_id=patient_id,
        study_uid=str(datasets[0].StudyInstanceUID),
        series_uids=sorted({str(ds.SeriesInstanceUID) for ds in datasets}),
        pseudonym=deterministic_pseudonym(rule.pseudonym_salt, patient_id)
        if rule.pseudonymize
        else "",
    )


@pytest.mark.django_db
def test_delivery_sends_the_series_pseudonymized_with_the_xnat_project(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    task = _task(spool_root, images, RoutingRuleFactory.create(trial_protocol_id="XNATPROJ"))

    result = RouterTaskProcessor(task).process()

    assert result["status"] == DicomTask.Status.SUCCESS
    assert result["message"] == f"Sent {len(images)} images to {task.destination.name}."
    assert len(uploads.datasets) == len(images)
    sent = uploads.datasets[0]
    assert sent.PatientID == task.pseudonym
    assert sent.PatientComments.startswith(f"Project:XNATPROJ Subject:{task.pseudonym} ")
    task.refresh_from_db()
    assert sorted(task.sent_instance_uids) == sorted(str(ds.SOPInstanceUID) for ds in images)


@pytest.mark.django_db
def test_late_batch_gets_the_same_pseudonym_and_uids(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    rule = RoutingRuleFactory.create()
    first = _task(spool_root, images[:5], rule)
    late = _task(spool_root, images[5:], rule)

    RouterTaskProcessor(first).process()
    first_sent = list(uploads.datasets)
    uploads.datasets.clear()
    RouterTaskProcessor(late).process()

    assert {ds.PatientID for ds in first_sent + uploads.datasets} == {first.pseudonym}
    assert {ds.StudyInstanceUID for ds in first_sent} == {
        ds.StudyInstanceUID for ds in uploads.datasets
    }
    assert first_sent[0].StudyInstanceUID != images[0].StudyInstanceUID


@pytest.mark.django_db
def test_images_sent_before_are_left_out(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    rule = RoutingRuleFactory.create()
    earlier = _task(spool_root, images, rule)
    RouterTask.objects.filter(pk=earlier.pk).update(
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=[str(ds.SOPInstanceUID) for ds in images[:4]],
    )

    RouterTaskProcessor(_task(spool_root, images, rule)).process()

    assert len(uploads.datasets) == len(images) - 4


@pytest.mark.django_db
def test_nothing_is_sent_when_every_image_was_sent_before(spool_root, mocker):
    uploads = _Uploads(mocker)
    images = _ct_images()
    rule = RoutingRuleFactory.create()
    earlier = _task(spool_root, images, rule)
    RouterTask.objects.filter(pk=earlier.pk).update(
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=[str(ds.SOPInstanceUID) for ds in images],
    )

    result = RouterTaskProcessor(_task(spool_root, images, rule)).process()

    assert result["status"] == DicomTask.Status.SUCCESS
    assert result["message"] == "Nothing new to send."
    assert uploads.datasets == []


@pytest.mark.django_db
def test_delivery_of_a_deleted_batch_fails_clearly(spool_root, mocker):
    _Uploads(mocker)
    task = _task(spool_root, _ct_images()[:1], RoutingRuleFactory.create())
    batch = task.job.batch
    batch.files_deleted_at = timezone.now()
    batch.save()

    with pytest.raises(DicomError, match="forward the study again"):
        RouterTaskProcessor(task).process()


@pytest.mark.django_db
def test_delivery_of_a_missing_batch_folder_fails_clearly(spool_root, mocker):
    _Uploads(mocker)
    task = _task(spool_root, _ct_images()[:1], RoutingRuleFactory.create())
    batch = task.job.batch
    spool.delete_batch(spool.batch_dir(spool_root, batch.sender_id, batch.batch_id))

    with pytest.raises(DicomError, match="forward the study again"):
        RouterTaskProcessor(task).process()


@pytest.mark.django_db
def test_delivery_requests_the_stored_transfer_syntax(spool_root, mocker):
    uploads = _Uploads(mocker)
    path = get_testdata_file("MR_small_jpeg_ls_lossless.dcm")
    assert isinstance(path, str)
    task = _task(spool_root, [read_dataset(path)], RoutingRuleFactory.create(pseudonymize=False))

    RouterTaskProcessor(task).process()

    assert uploads.store_contexts is not None
    assert [
        (str(cx.abstract_syntax), [str(ts) for ts in cx.transfer_syntax])
        for cx in uploads.store_contexts
    ] == [(MRImageStorage, [JPEGLSLossless])]
    assert uploads.datasets[0].file_meta.TransferSyntaxUID == JPEGLSLossless


@pytest.mark.django_db
def test_router_tasks_queue_on_the_dicom_queue():
    task = RouterTaskFactory.create()

    task.queue_pending_task()

    row = ProcrastinateJob.objects.get(pk=task.queued_job_id)
    assert row.task_name == "adit.router.tasks.process_router_task"
    assert row.queue_name == "dicom"
    assert row.priority == settings.ROUTER_DEFAULT_PRIORITY


@pytest.mark.django_db
def test_router_job_queues_its_pending_tasks():
    task = RouterTaskFactory.create()

    task.job.queue_pending_tasks()

    task.refresh_from_db()
    assert task.queued_job is not None


def test_stale_task_sweep_covers_router_tasks():
    assert RouterTask in dicom_task_models()
