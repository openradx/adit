import os
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from adit.core.models import DicomJob, DicomTask
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.factories import (
    RouterBatchFactory,
    RouterJobFactory,
    RouterSenderFactory,
    RouterTaskFactory,
    RoutingRuleFactory,
)
from adit.router.models import RouterBatch, RouterJob, RouterSettings, RouterTask
from adit.router.utils import closer, spool


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def _batch_with_jobs(spool_root: Path, *statuses: str, days_ago: int = 0) -> RouterBatch:
    batch = RouterBatchFactory.create()
    for status in statuses:
        RouterJobFactory.create(batch=batch, status=status)
    RouterBatch.objects.filter(pk=batch.pk).update(
        closed_at=timezone.now() - timedelta(days=days_ago)
    )
    batch.refresh_from_db()
    spool.batch_dir(spool_root, batch.sender_id, batch.batch_id).mkdir(parents=True)
    return batch


@pytest.mark.django_db
def test_cycle_closes_quiet_studies_and_decides_them(spool_root):
    sender = RouterSenderFactory.create()
    RoutingRuleFactory.create()  # CT
    for ds in load_sample_dicoms("1004"):
        spool.store_dataset(spool_root, sender.pk, ds)

    closer.run_spool_cycle(spool_root, timezone.now() + timedelta(hours=2))

    assert RouterJob.objects.count() == 1
    assert list((spool_root / spool.INCOMING / str(sender.pk)).iterdir()) == []


@pytest.mark.django_db
def test_cycle_leaves_recent_studies_open(spool_root):
    sender = RouterSenderFactory.create()
    RoutingRuleFactory.create()
    for ds in list(load_sample_dicoms("1004"))[:1]:
        spool.store_dataset(spool_root, sender.pk, ds)

    closer.run_spool_cycle(spool_root, timezone.now())

    assert not RouterJob.objects.exists()


@pytest.mark.django_db
def test_cycle_removes_old_tmp_files(spool_root):
    leftover = spool_root / spool.TMP / "leftover.dcm"
    leftover.write_bytes(b"x")
    two_hours_ago = (timezone.now() - timedelta(hours=2)).timestamp()
    os.utime(leftover, (two_hours_ago, two_hours_ago))

    closer.run_spool_cycle(spool_root, timezone.now())

    assert not leftover.exists()


@pytest.mark.django_db
def test_delivered_batches_are_deleted(spool_root):
    batch = _batch_with_jobs(spool_root, DicomJob.Status.SUCCESS, DicomJob.Status.CANCELED)
    now = timezone.now()

    assert closer.delete_finished_batches(spool_root, now) == 1

    batch.refresh_from_db()
    assert batch.files_deleted_at == now
    assert not spool.batch_dir(spool_root, batch.sender_id, batch.batch_id).exists()


@pytest.mark.django_db
def test_batches_with_running_deliveries_are_kept(spool_root):
    _batch_with_jobs(spool_root, DicomJob.Status.SUCCESS, DicomJob.Status.IN_PROGRESS)

    assert closer.delete_finished_batches(spool_root, timezone.now()) == 0


@pytest.mark.django_db
def test_failed_batches_are_kept_until_their_retention_ends(spool_root, settings):
    settings.ROUTER_FAILED_RETENTION_DAYS = 7
    recent = _batch_with_jobs(spool_root, DicomJob.Status.FAILURE, days_ago=6)
    old = _batch_with_jobs(spool_root, DicomJob.Status.FAILURE, DicomJob.Status.SUCCESS, days_ago=8)

    assert closer.delete_finished_batches(spool_root, timezone.now()) == 1

    recent.refresh_from_db()
    old.refresh_from_db()
    assert recent.files_deleted_at is None
    assert old.files_deleted_at is not None


@pytest.mark.django_db
def test_low_space_mails_the_admins_at_most_once_per_period(spool_root, mocker, settings):
    settings.ROUTER_LOW_SPACE_MAIL_HOURS = 6
    mocker.patch.object(closer.spool, "free_bytes", return_value=0)
    mail = mocker.patch.object(closer, "send_mail_to_admins")
    now = timezone.now()

    assert closer.mail_if_low_on_space(spool_root, now)
    assert not closer.mail_if_low_on_space(spool_root, now + timedelta(hours=5))
    assert closer.mail_if_low_on_space(spool_root, now + timedelta(hours=7))

    assert mail.call_count == 2
    router_settings = RouterSettings.get()
    assert isinstance(router_settings, RouterSettings)
    assert router_settings.low_space_mailed_at == now + timedelta(hours=7)


@pytest.mark.django_db
def test_enough_space_sends_no_mail(spool_root, mocker):
    mocker.patch.object(closer.spool, "free_bytes", return_value=100 * 1024**3)
    mail = mocker.patch.object(closer, "send_mail_to_admins")

    assert not closer.mail_if_low_on_space(spool_root, timezone.now())

    mail.assert_not_called()


@pytest.mark.django_db
def test_failed_deliveries_of_the_last_day_are_reported(mocker, settings):
    settings.ROUTER_FAILED_RETENTION_DAYS = 7
    mail = mocker.patch.object(closer, "send_mail_to_admins")
    now = timezone.now()
    failed = RouterTaskFactory.create(
        status=DicomTask.Status.FAILURE, message="Could not connect to the destination."
    )
    RouterJob.objects.filter(pk=failed.job.pk).update(
        status=DicomJob.Status.FAILURE, end=now - timedelta(hours=2)
    )
    old = RouterTaskFactory.create(status=DicomTask.Status.FAILURE)
    RouterJob.objects.filter(pk=old.job.pk).update(
        status=DicomJob.Status.FAILURE, end=now - timedelta(days=2)
    )

    assert closer.report_failed_deliveries(now) == 1

    subject, text = mail.call_args.args
    assert subject == "1 DICOM router deliveries failed"
    assert f"Job {failed.job.pk}" in text
    assert failed.job.rule.name in text
    assert "Could not connect to the destination." in text
    assert f"Job {old.job.pk}" not in text


@pytest.mark.django_db
def test_no_failures_send_no_report(mocker):
    mail = mocker.patch.object(closer, "send_mail_to_admins")

    assert closer.report_failed_deliveries(timezone.now()) == 0

    mail.assert_not_called()


@pytest.mark.django_db
def test_old_sent_lists_are_cleared(settings):
    settings.ROUTER_SENT_LIST_RETENTION_DAYS = 30
    now = timezone.now()
    old = RouterTaskFactory.create(sent_instance_uids=["1.1"], end=now - timedelta(days=31))
    recent = RouterTaskFactory.create(sent_instance_uids=["1.2"], end=now - timedelta(days=29))

    assert closer.clear_old_sent_lists(now) == 1

    assert RouterTask.objects.get(pk=old.pk).sent_instance_uids == []
    assert RouterTask.objects.get(pk=recent.pk).sent_instance_uids == ["1.2"]
