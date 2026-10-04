import errno
import os
import stat
import uuid
from datetime import date
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config
from pydicom.dataset import FileMetaDataset
from pydicom.uid import UID, CTImageStorage, ExplicitVRLittleEndian, generate_uid

from adit.core.utils.dicom_utils import read_dataset
from adit.router.utils import spool


def _dataset(study_uid: str | None = None, instance_uid: str | None = None) -> Dataset:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = instance_uid or generate_uid()
    ds.StudyInstanceUID = study_uid or generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientID = "1001"
    ds.Modality = "CT"
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = UID(ds.SOPInstanceUID)
    return ds


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def test_ensure_spool_dirs_creates_the_layout(tmp_path):
    spool.ensure_spool_dirs(tmp_path)

    for name in (spool.TMP, spool.INCOMING, spool.BATCHES, spool.QUARANTINE):
        assert (tmp_path / name).is_dir()


def test_ensure_spool_dirs_closes_an_existing_spool_to_others(tmp_path):
    incoming = tmp_path / spool.INCOMING
    incoming.mkdir()
    incoming.chmod(0o755)

    spool.ensure_spool_dirs(tmp_path)

    assert stat.S_IMODE(incoming.stat().st_mode) == 0o700


def test_store_dataset_writes_into_the_senders_study_folder(spool_root):
    ds = _dataset()

    path = spool.store_dataset(spool_root, 7, ds)

    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert read_dataset(path).SOPInstanceUID == ds.SOPInstanceUID


def test_store_dataset_leaves_nothing_in_tmp(spool_root):
    spool.store_dataset(spool_root, 7, _dataset())

    assert list((spool_root / spool.TMP).iterdir()) == []


def test_spooled_images_are_only_readable_by_the_owner(spool_root):
    path = spool.store_dataset(spool_root, 7, _dataset())

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_resending_an_image_replaces_it(spool_root):
    study_uid, instance_uid = generate_uid(), generate_uid()

    spool.store_dataset(spool_root, 7, _dataset(study_uid, instance_uid))
    spool.store_dataset(spool_root, 7, _dataset(study_uid, instance_uid))

    study_dir = spool_root / spool.INCOMING / "7" / study_uid
    assert [p.name for p in study_dir.iterdir()] == [f"{instance_uid}.dcm"]


@pytest.mark.parametrize("field", ["StudyInstanceUID", "SOPInstanceUID"])
@pytest.mark.parametrize("bad_uid", ["", "../../etc", "1.2.x", "1..2", "1" * 65, None])
def test_store_dataset_refuses_uids_that_are_not_path_safe(spool_root, field, bad_uid):
    ds = _dataset()
    if bad_uid is None:
        delattr(ds, field)
    else:
        with pydicom_config.disable_value_validation():
            delattr(ds, field)
            setattr(ds, field, bad_uid)

    with pytest.raises(spool.InvalidUidError):
        spool.store_dataset(spool_root, 7, ds)

    assert list((spool_root / spool.TMP).iterdir()) == []
    assert list((spool_root / spool.INCOMING).iterdir()) == []


def test_image_arriving_while_its_study_folder_closes_starts_a_new_folder(spool_root, monkeypatch):
    """The closing task (stage 3) renames a quiet study folder to batches/. If that
    happens between the router creating the folder and moving the image in, the move
    fails and the image lands in a fresh study folder: the next batch."""
    ds = _dataset()
    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    closed_dir = spool_root / spool.BATCHES / "7" / "closed"
    closed_dir.parent.mkdir(parents=True)
    real_replace = os.replace
    targets: list[str] = []

    def replace_racing_with_close(src, dst):
        if not targets:
            os.rename(study_dir, closed_dir)
        targets.append(str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(spool.os, "replace", replace_racing_with_close)

    path = spool.store_dataset(spool_root, 7, ds)

    assert len(targets) == 2
    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert path.is_file()
    assert list(closed_dir.iterdir()) == []


def test_a_failed_write_leaves_no_partial_file(spool_root, monkeypatch):
    def write_then_fail(ds, f):
        f.write(b"partial")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(spool, "write_dataset", write_then_fail)

    with pytest.raises(OSError):
        spool.store_dataset(spool_root, 7, _dataset())

    assert list((spool_root / spool.TMP).iterdir()) == []
    assert list((spool_root / spool.INCOMING).rglob("*.dcm")) == []


def test_clean_tmp_removes_leftovers_of_a_crash(spool_root):
    (spool_root / spool.TMP / "abc.dcm").write_bytes(b"partial")

    assert spool.clean_tmp(spool_root) == 1
    assert list((spool_root / spool.TMP).iterdir()) == []


def test_free_bytes_reports_the_spool_filesystem(spool_root):
    assert spool.free_bytes(spool_root) > 0


@pytest.mark.parametrize("value", ["1.2.3\n", "1.2.3 ", "\n1.2.3", "1.2.3\x00"])
def test_is_valid_uid_requires_the_whole_value_to_be_a_uid(value):
    assert not spool.is_valid_uid(value)


@pytest.mark.parametrize("value", ["1", "1.2.840.10008.1.2", "9" * 64])
def test_is_valid_uid_accepts_uids(value):
    assert spool.is_valid_uid(value)


def test_file_moved_into_a_recreated_study_folder_is_still_made_durable(spool_root, monkeypatch):
    """Store A opens the study folder, the closing task renames it to batches/, and
    store B re-creates it before A moves its file in. The file lands in the new folder,
    which A's folder fd doesn't point to, so A must fall back to a full sync."""
    ds = _dataset()
    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    closed_dir = spool_root / spool.BATCHES / "7" / "closed"
    closed_dir.parent.mkdir(parents=True)
    real_replace = os.replace
    syncs: list[str] = []

    def replace_after_close_and_recreate(src, dst):
        if not closed_dir.exists():
            os.rename(study_dir, closed_dir)
            study_dir.mkdir()
        return real_replace(src, dst)

    monkeypatch.setattr(spool.os, "replace", replace_after_close_and_recreate)
    monkeypatch.setattr(spool.os, "sync", lambda: syncs.append("sync"))

    path = spool.store_dataset(spool_root, 7, ds)

    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert path.is_file()
    assert list(closed_dir.iterdir()) == []
    assert syncs == ["sync"]


def test_file_and_folder_are_flushed_around_the_move(spool_root, monkeypatch):
    events: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def recording_fsync(fd):
        events.append("dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        real_fsync(fd)

    def recording_replace(src, dst):
        events.append("replace")
        real_replace(src, dst)

    monkeypatch.setattr(spool.os, "fsync", recording_fsync)
    monkeypatch.setattr(spool.os, "replace", recording_replace)

    spool.store_dataset(spool_root, 7, _dataset())

    assert events.index("file") < events.index("replace")
    assert events[events.index("replace") + 1 :] == ["dir"]


def test_gives_up_when_the_study_folder_keeps_closing(spool_root, monkeypatch):
    ds = _dataset()
    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    closed = spool_root / spool.BATCHES / "7"
    closed.mkdir(parents=True)
    real_replace = os.replace
    attempts: list[int] = []

    def replace_always_after_close(src, dst):
        attempts.append(1)
        os.rename(study_dir, closed / f"closed-{len(attempts)}")
        return real_replace(src, dst)

    monkeypatch.setattr(spool.os, "replace", replace_always_after_close)

    with pytest.raises(spool.SpoolError):
        spool.store_dataset(spool_root, 7, ds)

    assert len(attempts) == 5
    assert list((spool_root / spool.TMP).iterdir()) == []
    assert all(not any(folder.iterdir()) for folder in closed.iterdir())


def test_parent_folder_vanishing_while_the_study_folder_is_created_is_retried(
    spool_root, monkeypatch
):
    ds = _dataset()
    real_ensure_dir = spool._ensure_dir
    calls: list[Path] = []

    def ensure_dir_racing_with_cleanup(path: Path) -> None:
        calls.append(path)
        if len(calls) == 1:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory", str(path.parent))
        real_ensure_dir(path)

    monkeypatch.setattr(spool, "_ensure_dir", ensure_dir_racing_with_cleanup)

    path = spool.store_dataset(spool_root, 7, ds)

    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert path.is_file()


def _age(path, seconds_ago: float, now: float) -> None:
    os.utime(path, (now - seconds_ago, now - seconds_ago))


def _open_study(spool_root, sender_id=7, images=1):
    paths = [
        spool.store_dataset(spool_root, sender_id, _dataset(study_uid="1.2.3"))
        for _ in range(images)
    ]
    return paths[0].parent


def test_quiet_study_closes_into_a_batch(spool_root):
    study_dir = _open_study(spool_root, images=2)
    now = study_dir.stat().st_mtime + 301

    [batch] = spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600)

    assert batch.sender_id == 7
    assert batch.path == spool.batch_dir(spool_root, 7, batch.batch_id)
    assert len(list(batch.path.iterdir())) == 2
    assert not study_dir.exists()
    assert (spool_root / spool.INCOMING / "7").is_dir()


def test_study_that_got_an_image_recently_stays_open(spool_root):
    study_dir = _open_study(spool_root)
    now = study_dir.stat().st_mtime + 10

    assert spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600) == []
    assert study_dir.is_dir()


def test_study_open_too_long_closes_even_while_images_arrive(spool_root):
    study_dir = _open_study(spool_root)
    now = study_dir.stat().st_mtime + 10
    for path in study_dir.iterdir():
        _age(path, 4000, now)

    [batch] = spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600)

    assert batch.path.is_dir()


def test_quiet_empty_study_folder_is_removed(spool_root):
    study_dir = spool_root / spool.INCOMING / "7" / "1.2.3"
    study_dir.mkdir(parents=True)
    now = study_dir.stat().st_mtime + 301

    assert spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600) == []
    assert not study_dir.exists()


def test_one_broken_folder_does_not_stop_the_others_from_closing(spool_root, monkeypatch):
    spool.store_dataset(spool_root, 7, _dataset(study_uid="1.2.3"))
    spool.store_dataset(spool_root, 7, _dataset(study_uid="1.2.4"))
    sender_dir = spool_root / spool.INCOMING / "7"
    now = max(p.stat().st_mtime for p in sender_dir.rglob("*.dcm")) + 301
    real_rename = os.rename

    def rename_failing_for_one_study(src, dst):
        if Path(src).name == "1.2.3":
            raise OSError("Simulated rename failure.")
        return real_rename(src, dst)

    monkeypatch.setattr(spool.os, "rename", rename_failing_for_one_study)

    closed = spool.close_due_studies(spool_root, now, quiet_seconds=300, max_open_seconds=3600)

    assert len(closed) == 1
    assert closed[0].path.name != "1.2.3"
    # The broken folder is untouched and tried again on the next cycle.
    assert (sender_dir / "1.2.3").is_dir()


def test_image_arriving_after_closing_starts_the_next_batch(spool_root):
    study_dir = _open_study(spool_root)
    spool.close_due_studies(
        spool_root, study_dir.stat().st_mtime + 301, quiet_seconds=300, max_open_seconds=3600
    )

    path = spool.store_dataset(spool_root, 7, _dataset(study_uid="1.2.3"))

    assert path.parent == study_dir
    assert len(spool.list_batches(spool_root)) == 1


def test_list_batches_ignores_foreign_folders(spool_root):
    batch_id = uuid.uuid4()
    spool.batch_dir(spool_root, 7, batch_id).mkdir(parents=True)
    (spool_root / spool.BATCHES / "7" / "not-a-uuid").mkdir()
    (spool_root / spool.BATCHES / "lost+found").mkdir()

    assert spool.list_batches(spool_root) == [
        spool.BatchDir(7, batch_id, spool.batch_dir(spool_root, 7, batch_id))
    ]


def test_delete_batch_tolerates_a_folder_that_is_already_gone(spool_root):
    path = spool.batch_dir(spool_root, 7, uuid.uuid4())

    spool.delete_batch(path)

    assert not path.exists()


def test_quarantine_keeps_files_until_their_retention_ends(spool_root):
    bad = spool_root / spool.TMP / "bad.dcm"
    bad.write_bytes(b"not dicom")

    moved = spool.quarantine_file(spool_root, bad, date(2026, 10, 1))

    assert moved.parent == spool_root / spool.QUARANTINE / "20261001"
    assert moved.read_bytes() == b"not dicom"
    assert spool.clean_quarantine(spool_root, date(2026, 10, 8), retention_days=7) == 0
    assert spool.clean_quarantine(spool_root, date(2026, 10, 9), retention_days=7) == 1
    assert not moved.parent.exists()


def test_clean_old_tmp_spares_files_being_written(spool_root):
    old = spool_root / spool.TMP / "old.dcm"
    new = spool_root / spool.TMP / "new.dcm"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    now = new.stat().st_mtime + 10
    _age(old, 3700, now)

    assert spool.clean_old_tmp(spool_root, now, max_age_seconds=3600) == 1
    assert not old.exists()
    assert new.exists()
