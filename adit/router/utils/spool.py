"""The router's spool: images on disk between receiving and routing.

All folders live on one filesystem, so moving a file or folder inside the spool is a
single atomic rename. The spool holds identifiable images, so only its owner may read it.
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
        and _UID_PATTERN.fullmatch(value) is not None
    )


def ensure_spool_dirs(spool_root: Path) -> None:
    for name in (TMP, INCOMING, BATCHES, QUARANTINE):
        path = spool_root / name
        _ensure_dir(path)
        path.chmod(0o700)


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
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            write_dataset(ds, f)
            f.flush()
            os.fsync(f.fileno())
            file_stat = os.fstat(f.fileno())
        study_dir = incoming_study_dir(spool_root, sender_id, study_uid)
        return _move_into_study_dir(tmp_path, file_stat, study_dir, f"{instance_uid}.dcm")
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


def _move_into_study_dir(
    tmp_path: Path, file_stat: os.stat_result, study_dir: Path, filename: str
) -> Path:
    for _ in range(_MAX_MOVE_ATTEMPTS):
        try:
            _ensure_dir(study_dir)
            # Opened before the move so the fsync reaches the folder even if it is
            # renamed to batches/ right after the move.
            dir_fd = os.open(study_dir, os.O_RDONLY)
        except FileNotFoundError:
            continue
        try:
            try:
                os.replace(tmp_path, study_dir / filename)
            except FileNotFoundError:
                continue
            _fsync_moved_entry(dir_fd, filename, file_stat)
            return study_dir / filename
        finally:
            os.close(dir_fd)
    raise SpoolError(f"Could not move {filename} into {study_dir}.")


def _fsync_moved_entry(dir_fd: int, filename: str, file_stat: os.stat_result) -> None:
    """Make the folder entry of the moved file durable.

    The file normally lands in the folder dir_fd points to. If that folder was closed and
    re-created by another store in between, the file is in the new folder, which may already
    have been closed again; only a full sync reliably covers that case.
    """
    try:
        landed_here = os.path.samestat(os.stat(filename, dir_fd=dir_fd), file_stat)
    except FileNotFoundError:
        landed_here = False
    if landed_here:
        os.fsync(dir_fd)
    else:
        os.sync()


def _ensure_dir(path: Path) -> None:
    """Create *path* and its parents, flushing each new folder entry to disk."""
    if path.is_dir():
        return
    _ensure_dir(path.parent)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    # Also after FileExistsError: the store that created the folder may not have
    # flushed its entry yet.
    _fsync_dir(path.parent)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
