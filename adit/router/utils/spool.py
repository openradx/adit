"""The router's spool: images on disk between receiving and routing.

All folders live on one filesystem, so moving a file or folder inside the spool is a
single atomic rename. The spool holds identifiable images, so only its owner may read it.
"""

import logging
import os
import re
import shutil
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from pydicom import Dataset

from adit.core.utils.dicom_utils import write_dataset

logger = logging.getLogger(__name__)

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
        # clean_old_tmp (the default worker) may delete the same file concurrently.
        path.unlink(missing_ok=True)
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


class BatchDir(NamedTuple):
    sender_id: int
    batch_id: uuid.UUID
    path: Path


def batch_dir(spool_root: Path, sender_id: int, batch_id: uuid.UUID) -> Path:
    return spool_root / BATCHES / str(sender_id) / str(batch_id)


def close_due_studies(
    spool_root: Path, now: float, quiet_seconds: int, max_open_seconds: int
) -> list[BatchDir]:
    """Close every study folder that is due and return the batches made from them.

    A folder is due when its modification time, which every image moved in updates, is
    *quiet_seconds* old, or when its oldest file is *max_open_seconds* old. Closing
    renames it into batches/<sender id>/<new uuid>/, so an image moved in at the same
    time lands either in the batch or, retried by the store, in a new study folder.
    Empty study folders, left by a store whose move failed, are removed once quiet.
    """
    closed: list[BatchDir] = []
    for sender_id, sender_dir in _sender_dirs(spool_root / INCOMING):
        for study_dir in _subdirs(sender_dir):
            try:
                batch = _close_if_due(
                    spool_root, sender_id, study_dir, now, quiet_seconds, max_open_seconds
                )
            except Exception:
                # One broken folder must not hold up the others; the next run retries it.
                logger.exception("Could not close router study folder %s.", study_dir)
                continue
            if batch is not None:
                closed.append(batch)
    return closed


def list_batches(spool_root: Path) -> list[BatchDir]:
    batches: list[BatchDir] = []
    for sender_id, sender_dir in _sender_dirs(spool_root / BATCHES):
        for path in _subdirs(sender_dir):
            try:
                batch_id = uuid.UUID(path.name)
            except ValueError:
                logger.warning("Ignoring %s: not a router batch folder.", path)
                continue
            batches.append(BatchDir(sender_id, batch_id, path))
    return batches


def delete_batch(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def quarantine_file(spool_root: Path, path: Path, today: date) -> Path:
    """Move an unreadable file to quarantine/<YYYYMMDD>/ and return its new path."""
    target_dir = spool_root / QUARANTINE / today.strftime("%Y%m%d")
    _ensure_dir(target_dir)
    target = target_dir / f"{uuid.uuid4().hex}_{path.name}"
    os.replace(path, target)
    return target


def clean_quarantine(spool_root: Path, today: date, retention_days: int) -> int:
    """Delete the quarantine days older than *retention_days*; returns how many."""
    oldest_kept = today - timedelta(days=retention_days)
    removed = 0
    for day_dir in _subdirs(spool_root / QUARANTINE):
        try:
            day = datetime.strptime(day_dir.name, "%Y%m%d").date()
        except ValueError:
            continue
        if day < oldest_kept:
            shutil.rmtree(day_dir)
            removed += 1
    return removed


def clean_old_tmp(spool_root: Path, now: float, max_age_seconds: int) -> int:
    """Delete files in tmp/ older than *max_age_seconds*; returns how many.

    The router empties tmp/ when it starts. This catches files left behind while it
    runs, without touching the ones it is writing.
    """
    removed = 0
    for path in (spool_root / TMP).iterdir():
        try:
            if now - path.stat().st_mtime >= max_age_seconds:
                path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
    return removed


def _close_if_due(
    spool_root: Path,
    sender_id: int,
    study_dir: Path,
    now: float,
    quiet_seconds: int,
    max_open_seconds: int,
) -> BatchDir | None:
    try:
        quiet = now - study_dir.stat().st_mtime >= quiet_seconds
        file_times = [p.stat().st_mtime for p in study_dir.iterdir() if p.is_file()]
    except FileNotFoundError:
        return None

    if not file_times:
        if quiet:
            try:
                study_dir.rmdir()
            except OSError:
                pass  # an image was moved in meanwhile
        return None

    if not quiet and now - min(file_times) < max_open_seconds:
        return None

    batch_id = uuid.uuid4()
    target = batch_dir(spool_root, sender_id, batch_id)
    _ensure_dir(target.parent)
    os.rename(study_dir, target)
    _fsync_dir(study_dir.parent)
    _fsync_dir(target.parent)
    return BatchDir(sender_id, batch_id, target)


def _sender_dirs(path: Path) -> list[tuple[int, Path]]:
    sender_dirs: list[tuple[int, Path]] = []
    for sender_dir in _subdirs(path):
        try:
            sender_dirs.append((int(sender_dir.name), sender_dir))
        except ValueError:
            logger.warning("Ignoring %s: not a router sender folder.", sender_dir)
    return sender_dirs


def _subdirs(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_dir())
