import errno
import os
import warnings
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

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
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID  # type: ignore
    return ds


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def test_ensure_spool_dirs_creates_the_layout(tmp_path):
    spool.ensure_spool_dirs(tmp_path)

    for name in (spool.TMP, spool.INCOMING, spool.BATCHES, spool.QUARANTINE):
        assert (tmp_path / name).is_dir()


def test_store_dataset_writes_into_the_senders_study_folder(spool_root):
    ds = _dataset()

    path = spool.store_dataset(spool_root, 7, ds)

    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert read_dataset(path).SOPInstanceUID == ds.SOPInstanceUID


def test_store_dataset_leaves_nothing_in_tmp(spool_root):
    spool.store_dataset(spool_root, 7, _dataset())

    assert list((spool_root / spool.TMP).iterdir()) == []


def test_resending_an_image_replaces_it(spool_root):
    study_uid, instance_uid = generate_uid(), generate_uid()

    spool.store_dataset(spool_root, 7, _dataset(study_uid, instance_uid))
    spool.store_dataset(spool_root, 7, _dataset(study_uid, instance_uid))

    study_dir = spool_root / spool.INCOMING / "7" / study_uid
    assert [p.name for p in study_dir.iterdir()] == [f"{instance_uid}.dcm"]


@pytest.mark.parametrize("bad_uid", ["", "../../etc", "1.2.x", "1..2", "1" * 65, None])
def test_store_dataset_refuses_uids_that_are_not_path_safe(spool_root, bad_uid):
    ds = _dataset()
    if bad_uid is None:
        del ds.StudyInstanceUID
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pydicom_config.disable_value_validation():
                ds.StudyInstanceUID = bad_uid

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
