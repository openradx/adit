import errno
import os
import stat
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
