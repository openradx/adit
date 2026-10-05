import uuid
from datetime import date
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config

from adit.core.models import DicomTask
from adit.core.utils.dicom_utils import write_dataset
from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.factories import (
    RouterJobFactory,
    RouterSenderFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterBatch, RouterJob, RouterSender, RouterTask
from adit.router.utils import spool
from adit.router.utils.routing import decide_batch

TODAY = date(2026, 10, 4)


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def _closed_batch(
    spool_root: Path, sender: RouterSender, datasets: list[Dataset]
) -> spool.BatchDir:
    batch_id = uuid.uuid4()
    path = spool.batch_dir(spool_root, sender.pk, batch_id)
    path.mkdir(parents=True)
    for ds in datasets:
        write_dataset(ds, path / f"{ds.SOPInstanceUID}.dcm")
    return spool.BatchDir(sender.pk, batch_id, path)


def _study() -> list[Dataset]:
    return list(load_sample_dicoms("1001"))  # CT x10 and one SR


@pytest.mark.django_db
def test_matching_rule_creates_a_queued_delivery(spool_root):
    sender = RouterSenderFactory.create()
    rule = RoutingRuleFactory.create(trial_protocol_id="XNATPROJ")  # CT only
    datasets = _study()
    batch = _closed_batch(spool_root, sender, datasets)

    [job] = decide_batch(spool_root, batch, TODAY)

    assert job.rule == rule
    assert job.owner == rule.created_by
    assert job.status == RouterJob.Status.PENDING
    assert job.trial_protocol_id == "XNATPROJ"
    task = job.tasks.get()
    assert set(task.series_uids) == {
        str(ds.SeriesInstanceUID) for ds in datasets if ds.Modality == "CT"
    }
    assert task.pseudonym == deterministic_pseudonym(rule.pseudonym_salt, "1001")
    assert task.source_id == sender.server.pk
    assert task.destination_id == rule.destination.pk
    assert task.queued_job is not None
    assert task.queued_job.task_name == "adit.router.tasks.process_router_task"
    assert RouterBatch.objects.get(batch_id=batch.batch_id).number_of_images == len(datasets)
    assert batch.path.is_dir()


@pytest.mark.django_db
def test_batch_no_rule_matches_is_deleted(spool_root):
    RoutingRuleFactory.create(filters_json=[{"modality": "MR"}])
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()
    assert not RouterBatch.objects.exists()


@pytest.mark.django_db
def test_disabled_rules_are_ignored(spool_root):
    RoutingRuleFactory.create(enabled=False)
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()
    assert not RouterBatch.objects.exists()


@pytest.mark.django_db
def test_images_sent_before_are_not_routed_again(spool_root):
    rule = RoutingRuleFactory.create()
    datasets = _study()
    RouterTaskFactory.create(
        job=RouterJobFactory.create(rule=rule),
        destination=rule.destination,
        study_uid=str(datasets[0].StudyInstanceUID),
        status=DicomTask.Status.SUCCESS,
        sent_instance_uids=[str(ds.SOPInstanceUID) for ds in datasets if ds.Modality == "CT"],
    )
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), datasets)

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()


@pytest.mark.django_db
def test_a_batch_is_decided_only_once(spool_root):
    RoutingRuleFactory.create()
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())
    decide_batch(spool_root, batch, TODAY)

    assert decide_batch(spool_root, batch, TODAY) == []
    assert RouterJob.objects.count() == 1


@pytest.mark.django_db
def test_batch_of_a_removed_sender_is_deleted(spool_root):
    RoutingRuleFactory.create()
    sender = RouterSenderFactory.create()
    batch = _closed_batch(spool_root, sender, _study())
    sender.delete()

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()


@pytest.mark.django_db
def test_study_without_patient_id_is_not_routed(spool_root):
    RoutingRuleFactory.create()
    datasets = _study()
    for ds in datasets:
        ds.PatientID = ""
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), datasets)

    assert decide_batch(spool_root, batch, TODAY) == []
    assert not batch.path.exists()
    assert not RouterBatch.objects.exists()


@pytest.mark.django_db
def test_patient_id_too_long_for_the_column_is_not_routed(spool_root):
    RoutingRuleFactory.create()
    datasets = _study()
    with pydicom_config.disable_value_validation():
        for ds in datasets:
            ds.PatientID = "1" * 65
        batch = _closed_batch(spool_root, RouterSenderFactory.create(), datasets)

        # Reading the over-long value back also validates it, under the same setting.
        assert decide_batch(spool_root, batch, TODAY) == []

    assert not batch.path.exists()
    assert not RouterBatch.objects.exists()


@pytest.mark.django_db
def test_rule_without_pseudonymization_sends_the_patient_as_is(spool_root):
    RoutingRuleFactory.create(pseudonymize=False)
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    [job] = decide_batch(spool_root, batch, TODAY)

    assert job.tasks.get().pseudonym == ""


@pytest.mark.django_db
def test_each_matching_rule_gets_its_own_delivery(spool_root):
    RoutingRuleFactory.create()
    RoutingRuleFactory.create(filters_json=[{"modality": "SR"}])
    batch = _closed_batch(spool_root, RouterSenderFactory.create(), _study())

    jobs = decide_batch(spool_root, batch, TODAY)

    assert len(jobs) == 2
    assert RouterTask.objects.count() == 2
