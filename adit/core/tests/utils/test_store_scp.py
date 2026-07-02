"""Unit tests for the C-STORE SCP receiver service (`adit.core.utils.store_scp`).

These tests exercise the *logic* of the store-event handler and the
connection/association lifecycle callbacks in isolation. They deliberately do
NOT stand up a real DICOM network listener (`AE.start_server`); instead the
pynetdicom `Event`/`Association` objects are faked and the
disk-write / file-transmit boundary is mocked.

What is covered:
  * A valid C-STORE event writes the dataset, attaches the file meta, invokes
    the registered file-received handler, and returns the DICOM `Success`
    (0x0000) status.
  * The calling AE title is retained as the temp-file prefix (the receiver
    relies on this for the file-transmit topic).
  * A disk-write failure aborts the association and returns `Out of Resources`
    (0xA702).
  * An out-of-disc-space (ENOSPC) failure also aborts and returns 0xA702.
  * A failure inside the file-received handler is swallowed and still returns
    `Success` (the file was stored successfully; forwarding is best-effort).
  * `start()` rejects an invalid storage folder.
  * The association lifecycle callbacks read the remote peer info without error.

What is NOT covered here (and why):
  * The actual pynetdicom socket / `AE.start_server` networking — that requires
    a live DIMSE peer and is exercised by the acceptance tests against Orthanc.
  * Real DICOM encoding of the received dataset — `write_dataset` is mocked so
    we can test the handler's control flow with synthetic datasets.
"""

import errno
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset

from adit.core.utils import store_scp as store_scp_module
from adit.core.utils.store_scp import StoreScp


def _make_event(
    *,
    calling_ae: str = "PACS1",
    address: str = "1.2.3.4",
    port: int = 11112,
    dataset: Dataset | None = None,
    file_meta: Dataset | None = None,
) -> MagicMock:
    """Build a fake pynetdicom C-STORE `Event`.

    Only the attributes that `StoreScp` actually reads are populated:
    `event.assoc.remote[...]`, `event.dataset`, `event.file_meta`, and the
    `event.assoc.abort()` method.
    """
    if dataset is None:
        dataset = Dataset()
        dataset.SOPInstanceUID = "1.2.3.4.5.6"
    if file_meta is None:
        file_meta = Dataset()

    event = MagicMock()
    event.assoc.remote = {
        "ae_title": calling_ae,
        "address": address,
        "port": port,
    }
    event.dataset = dataset
    event.file_meta = file_meta
    return event


@pytest.fixture
def store_scp(tmp_path: Path) -> StoreScp:
    return StoreScp(
        folder=tmp_path,
        ae_title="ADIT_RECEIVER",
        host="0.0.0.0",
        port=11112,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_handle_store_success_returns_success_status(store_scp, tmp_path, monkeypatch):
    """A valid C-STORE event returns the DICOM Success status (0x0000) and
    writes a file into the configured folder."""
    written: list[str] = []

    def fake_write_dataset(ds, fn):
        # Simulate a successful disk write by touching the file.
        with open(fn, "wb") as f:
            f.write(b"DICM")
        written.append(fn)

    monkeypatch.setattr(store_scp_module, "write_dataset", fake_write_dataset)

    event = _make_event(calling_ae="PACS1")
    status = store_scp._handle_store(event)

    assert status == 0x0000
    assert len(written) == 1
    # The file was created inside the storage folder.
    assert os.path.dirname(written[0]) == str(tmp_path)
    assert written[0].endswith(".dcm")


def test_handle_store_retains_calling_ae_as_filename_prefix(store_scp, monkeypatch):
    """The receiver depends on the calling AE title being encoded as the temp
    file prefix (`<AE>_...dcm`) so it can derive the file-transmit topic."""
    captured: list[str] = []

    def fake_write_dataset(ds, fn):
        captured.append(os.path.basename(fn))

    monkeypatch.setattr(store_scp_module, "write_dataset", fake_write_dataset)

    event = _make_event(calling_ae="REMOTE_PACS")
    store_scp._handle_store(event)

    assert len(captured) == 1
    assert captured[0].startswith("REMOTE_PACS_")
    # And the calling AE can be recovered the way receiver.py does it.
    assert captured[0].split("_")[0] == "REMOTE"  # split on first underscore


def test_handle_store_attaches_file_meta_to_dataset(store_scp, monkeypatch):
    """The handler must attach `event.file_meta` onto the dataset before it is
    written (the dataset arrives without file meta over the wire)."""
    seen_file_meta: list[FileMetaDataset] = []

    def fake_write_dataset(ds, fn):
        seen_file_meta.append(ds.file_meta)

    monkeypatch.setattr(store_scp_module, "write_dataset", fake_write_dataset)

    file_meta = Dataset()
    file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    event = _make_event(file_meta=file_meta)

    store_scp._handle_store(event)

    assert len(seen_file_meta) == 1
    # pydicom wraps the assigned Dataset into a FileMetaDataset (so it is a copy,
    # not the same identity), but the content must be preserved.
    assert seen_file_meta[0].TransferSyntaxUID == "1.2.840.10008.1.2.1"


def test_handle_store_invokes_file_received_handler_with_written_path(store_scp, monkeypatch):
    """On success the registered file-received handler is called with the path
    of the file that was just written."""
    monkeypatch.setattr(store_scp_module, "write_dataset", lambda ds, fn: None)

    received: list[str] = []
    store_scp.set_file_received_handler(lambda path: received.append(path))

    event = _make_event()
    status = store_scp._handle_store(event)

    assert status == 0x0000
    assert len(received) == 1
    assert received[0].endswith(".dcm")
    assert "PACS1_" in os.path.basename(received[0])


def test_handle_store_without_handler_still_succeeds(store_scp, monkeypatch):
    """If no file-received handler is registered the store still succeeds."""
    monkeypatch.setattr(store_scp_module, "write_dataset", lambda ds, fn: None)

    assert store_scp._file_received_handler is None
    event = _make_event()
    status = store_scp._handle_store(event)

    assert status == 0x0000


# ---------------------------------------------------------------------------
# Error / failure paths
# ---------------------------------------------------------------------------


def test_handle_store_write_failure_aborts_and_returns_out_of_resources(store_scp, monkeypatch):
    """A generic disk-write failure must abort the association and answer with
    the DICOM `Out of Resources` status (0xA702)."""

    def boom(ds, fn):
        raise RuntimeError("disk write blew up")

    monkeypatch.setattr(store_scp_module, "write_dataset", boom)

    event = _make_event()
    status = store_scp._handle_store(event)

    assert status == 0xA702
    event.assoc.abort.assert_called_once()


def test_handle_store_enospc_failure_aborts_and_returns_out_of_resources(store_scp, monkeypatch):
    """An out-of-disc-space (ENOSPC) error takes the dedicated branch, aborts
    the association, and also returns 0xA702."""

    def out_of_space(ds, fn):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(store_scp_module, "write_dataset", out_of_space)

    event = _make_event()
    status = store_scp._handle_store(event)

    assert status == 0xA702
    event.assoc.abort.assert_called_once()


def test_handle_store_handler_failure_is_swallowed_and_returns_success(store_scp, monkeypatch):
    """The file was written OK, but the file-received handler raises. The
    handler error is swallowed and the store still returns Success (0x0000) —
    forwarding to workers is best-effort and must not fail the C-STORE."""
    monkeypatch.setattr(store_scp_module, "write_dataset", lambda ds, fn: None)

    def failing_handler(path):
        raise ValueError("could not enqueue file")

    store_scp.set_file_received_handler(failing_handler)

    event = _make_event()
    status = store_scp._handle_store(event)

    assert status == 0x0000
    # The association must NOT be aborted on a mere forwarding failure.
    event.assoc.abort.assert_not_called()


def test_handle_store_write_failure_does_not_call_handler(store_scp, monkeypatch):
    """If the write fails, the file-received handler must not be invoked."""

    def boom(ds, fn):
        raise RuntimeError("nope")

    monkeypatch.setattr(store_scp_module, "write_dataset", boom)

    received: list[str] = []
    store_scp.set_file_received_handler(lambda path: received.append(path))

    event = _make_event()
    status = store_scp._handle_store(event)

    assert status == 0xA702
    assert received == []


# ---------------------------------------------------------------------------
# start() folder validation (no real server is started)
# ---------------------------------------------------------------------------


def test_start_rejects_nonexistent_folder():
    scp = StoreScp(
        folder=Path("/this/folder/definitely/does/not/exist"),
        ae_title="ADIT_RECEIVER",
        host="0.0.0.0",
        port=11112,
    )
    with pytest.raises(IOError, match="Invalid folder"):
        scp.start()


def test_start_rejects_file_as_folder(tmp_path):
    a_file = tmp_path / "not_a_dir.txt"
    a_file.write_text("x")
    scp = StoreScp(folder=a_file, ae_title="ADIT_RECEIVER", host="0.0.0.0", port=11112)
    with pytest.raises(IOError, match="Invalid folder"):
        scp.start()


# ---------------------------------------------------------------------------
# Association lifecycle callbacks
# ---------------------------------------------------------------------------


def test_lifecycle_callbacks_read_remote_peer_without_error(store_scp):
    """The connection/association event callbacks just log remote peer info;
    verify they don't raise given a well-formed event."""
    event = _make_event(calling_ae="PEER", address="10.0.0.9", port=4242)

    # None of these should raise.
    store_scp._on_connect(event)
    store_scp._on_close(event)
    store_scp._on_established(event)
    store_scp._on_released(event)
    store_scp._on_aborted(event)


def test_stop_is_safe_when_server_not_started(store_scp):
    """Calling stop() before start() must be a no-op (no AE was created)."""
    assert store_scp._ae is None
    store_scp.stop()  # should not raise
    assert store_scp._ae is None
