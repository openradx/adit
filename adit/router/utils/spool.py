"""The router's spool: images on disk between receiving and routing.

All folders live on one filesystem, so moving a file or folder inside the spool is a
single atomic rename.
"""

import os
import re
import shutil
import uuid
from pathlib import Path

from pydicom import Dataset

from adit.core.utils.dicom_utils import write_dataset

TMP = "tmp"
INCOMING = "incoming"
BATCHES = "batches"
QUARANTINE = "quarantine"

# UIDs become path components, so only the UID character set is accepted.
_UID_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_MAX_UID_LENGTH = 64

# A move into a study folder only fails when that folder is closed at the same
# moment, so a retry nearly always succeeds.
_MAX_MOVE_ATTEMPTS = 5


class InvalidUidError(ValueError):
    pass


class SpoolError(OSError):
    pass


def is_valid_uid(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= _MAX_UID_LENGTH
        and _UID_PATTERN.match(value) is not None
    )


def ensure_spool_dirs(spool_root: Path) -> None:
    for name in (TMP, INCOMING, BATCHES, QUARANTINE):
        (spool_root / name).mkdir(parents=True, exist_ok=True)


def incoming_study_dir(spool_root: Path, sender_id: int, study_uid: str) -> Path:
    return spool_root / INCOMING / str(sender_id) / study_uid


def store_dataset(spool_root: Path, sender_id: int, ds: Dataset) -> Path:
    """Write *ds* durably into its open study folder and return the file path.

    The file is written to tmp/ and flushed to disk first, then moved into the study
    folder, so a study folder never holds a partial file. When the study folder is
    closed between creating it and moving the file in, the move fails and the image
    starts a new study folder.
    """
    study_uid = ds.get("StudyInstanceUID")
    instance_uid = ds.get("SOPInstanceUID")
    if not is_valid_uid(study_uid) or not is_valid_uid(instance_uid):
        raise InvalidUidError(f"Invalid Study or SOP Instance UID: {study_uid!r}, {instance_uid!r}")

    tmp_path = spool_root / TMP / f"{uuid.uuid4().hex}.dcm"
    try:
        with open(tmp_path, "wb") as f:
            write_dataset(ds, f)
            f.flush()
            os.fsync(f.fileno())
        study_dir = incoming_study_dir(spool_root, sender_id, study_uid)
        return _move_into_study_dir(tmp_path, study_dir, f"{instance_uid}.dcm")
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def clean_tmp(spool_root: Path) -> int:
    """Delete files left in tmp/ by a crash while writing; returns how many."""
    removed = 0
    for path in (spool_root / TMP).iterdir():
        path.unlink()
        removed += 1
    return removed


def free_bytes(spool_root: Path) -> int:
    return shutil.disk_usage(spool_root).free


def _move_into_study_dir(tmp_path: Path, study_dir: Path, filename: str) -> Path:
    for _ in range(_MAX_MOVE_ATTEMPTS):
        _ensure_dir(study_dir)
        try:
            # Opened before the move so the fsync reaches the folder even if it is
            # renamed to batches/ right after the move.
            dir_fd = os.open(study_dir, os.O_RDONLY)
        except FileNotFoundError:
            continue
        try:
            os.replace(tmp_path, study_dir / filename)
            os.fsync(dir_fd)
            return study_dir / filename
        except FileNotFoundError:
            continue
        finally:
            os.close(dir_fd)
    raise SpoolError(f"Could not move {filename} into {study_dir}.")


def _ensure_dir(path: Path) -> None:
    """Create *path* and its parents, flushing each new folder entry to disk."""
    if path.is_dir():
        return
    _ensure_dir(path.parent)
    try:
        path.mkdir()
    except FileExistsError:
        return
    _fsync_dir(path.parent)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
