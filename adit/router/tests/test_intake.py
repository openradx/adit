import errno
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from adit.router.factories import RouterSenderFactory
from adit.router.models import RouterSender, RouterSettings
from adit.router.utils import spool
from adit.router.utils.intake import IntakeConfig, RouterStoreHandler, load_intake_config


def _event(calling_ae: str = "PACS1") -> MagicMock:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    event = MagicMock()
    event.assoc.remote = {"ae_title": calling_ae, "address": "10.0.0.1", "port": 104}
    event.dataset = ds
    event.file_meta = file_meta
    return event


def _spooled(spool_root: Path) -> list[Path]:
    return list((spool_root / spool.INCOMING).rglob("*.dcm"))


def _handler(spool_root: Path, min_free_bytes: int = 0) -> RouterStoreHandler:
    spool.ensure_spool_dirs(spool_root)
    handler = RouterStoreHandler(spool_root, min_free_bytes=min_free_bytes)
    handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=False))
    return handler


def test_image_from_an_enabled_sender_is_spooled(tmp_path):
    event = _event()

    assert _handler(tmp_path)(event) == 0x0000

    [path] = _spooled(tmp_path)
    assert path.parent == tmp_path / spool.INCOMING / "7" / event.dataset.StudyInstanceUID


def test_new_handler_refuses_everything_until_configured(tmp_path):
    spool.ensure_spool_dirs(tmp_path)
    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_sender_disabled_during_an_open_association_is_refused(tmp_path):
    handler = _handler(tmp_path)
    handler.update_config(IntakeConfig(sender_ids={}, suspended=False))

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_suspended_router_refuses_images(tmp_path):
    handler = _handler(tmp_path)
    handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=True))

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_low_spool_space_refuses_images(tmp_path):
    handler = _handler(tmp_path, min_free_bytes=10**18)

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_image_with_an_unsafe_uid_is_not_understood(tmp_path):
    event = _event()
    with pydicom_config.disable_value_validation():
        del event.dataset.StudyInstanceUID
        event.dataset.StudyInstanceUID = "../../etc"

    assert _handler(tmp_path)(event) == 0xC000
    assert _spooled(tmp_path) == []


def test_disk_full_while_writing_is_out_of_resources(tmp_path, monkeypatch):
    def disk_full(ds, f):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(spool, "write_dataset", disk_full)

    assert _handler(tmp_path)(_event()) == 0xA700
    assert list((tmp_path / spool.TMP).iterdir()) == []
    assert _spooled(tmp_path) == []


def test_image_that_cannot_be_encoded_is_not_understood(tmp_path, monkeypatch):
    def broken_encoding(ds, f):
        raise ValueError("cannot encode")

    monkeypatch.setattr(spool, "write_dataset", broken_encoding)

    assert _handler(tmp_path)(_event()) == 0xC000
    assert list((tmp_path / spool.TMP).iterdir()) == []
    assert _spooled(tmp_path) == []


@pytest.mark.django_db
def test_load_intake_config_lists_enabled_senders_and_the_suspended_flag():
    enabled = RouterSenderFactory.create(calling_ae_title="PACS1")
    RouterSenderFactory.create(calling_ae_title="OLDPACS", enabled=False)
    RouterSettings.objects.update(suspended=True)

    config = load_intake_config()

    assert config == IntakeConfig(sender_ids={"PACS1": enabled.pk}, suspended=True)


@pytest.mark.django_db
def test_missing_router_settings_keep_intake_suspended(caplog):
    sender = RouterSenderFactory.create(calling_ae_title="PACS1")
    RouterSettings.objects.all().delete()

    config = load_intake_config()

    assert config == IntakeConfig(sender_ids={"PACS1": sender.pk}, suspended=True)
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "The router settings are missing; intake stays suspended."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_title", ["PACS\tA", ""])
def test_load_intake_config_ignores_senders_with_an_invalid_ae_title(caplog, invalid_title):
    valid = RouterSenderFactory.create(calling_ae_title="PACS1")
    invalid = RouterSenderFactory.create(calling_ae_title="PACS2")
    # update() bypasses save(), which would replace an empty title.
    RouterSender.objects.filter(pk=invalid.pk).update(calling_ae_title=invalid_title)

    config = load_intake_config()

    assert config.sender_ids == {"PACS1": valid.pk}
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == [
        f"Router sender {invalid.pk} has an invalid AE title {invalid_title!r} and is ignored."
    ]
