import asyncio
import logging
import shutil
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock

import janus
import pytest
from aiofiles import os
from django.conf import settings
from pytest_django.fixtures import Settings

from adit.core.management.commands.receiver import Command, ReceivedFile, SyncRequest
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import (
    REPLAY_SYNC_TOKEN,
    FileTransmitClient,
    FileTransmitSession,
    Metadata,
)
from adit.core.utils.testing_helpers import stall_session, wait_until

HOST = "127.0.0.1"
PORT = 9997


@pytest.fixture
def received_file(tmp_path: Path) -> Path:
    sample_file = next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))
    return Path(shutil.copy(sample_file, tmp_path / "received.dcm"))


def _create_command(settings: Settings, port: int = PORT) -> Command:
    settings.FILE_TRANSMIT_PORT = port
    command = Command()
    command._queue = janus.Queue()
    command._file_transmit = command._create_file_transmit()
    return command


async def _close_queue(command: Command):
    command._queue.close()
    await command._queue.wait_closed()


@pytest.mark.asyncio
async def test_send_files_routes_on_study_instance_uid(received_file: Path, settings: Settings):
    ds = read_dataset(received_file)
    study_uid = ds.StudyInstanceUID

    command = _create_command(settings)
    server_task = asyncio.create_task(command._file_transmit.start())
    await asyncio.sleep(0.5)

    subscribed = asyncio.Event()
    received: list[Metadata] = []

    async def file_received_handler(filename: str, metadata: Metadata):
        received.append(metadata)
        await os.remove(filename)
        return True

    client = FileTransmitClient(HOST, PORT)
    client_task = asyncio.create_task(
        client.subscribe(study_uid, file_received_handler, subscribed_handler=subscribed.set)
    )
    await subscribed.wait()

    send_task = asyncio.create_task(command._send_files())
    try:
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        await asyncio.wait_for(client_task, timeout=5)
        await wait_until(lambda: not received_file.exists())
    finally:
        send_task.cancel()
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)

    # The series lets a worker tell the images of its series from others of the study
    assert received == [
        {
            "SOPInstanceUID": ds.SOPInstanceUID,
            "SeriesInstanceUID": ds.SeriesInstanceUID,
            "CallingAETitle": "PACS1",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("spool", [True, False])
async def test_send_files_warns_when_no_worker_is_subscribed(
    received_file: Path, settings: Settings, caplog: pytest.LogCaptureFixture, spool: bool
):
    study_uid = read_dataset(received_file).StudyInstanceUID
    command = _create_command(settings)
    if not spool:
        settings.RECEIVER_SPOOL_TTL = 0

    send_task = asyncio.create_task(command._send_files())
    try:
        with caplog.at_level(logging.WARNING):
            command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
            await wait_until(lambda: any(r.levelno == logging.WARNING for r in caplog.records))
    finally:
        send_task.cancel()
        await _close_queue(command)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert study_uid in warnings[0]
    assert "No worker subscribed" in warnings[0]
    assert ("keeping" if spool else "discarding") in warnings[0]
    assert received_file.exists() == spool


@pytest.mark.asyncio
async def test_the_dispatcher_moves_on_while_a_worker_is_stalled(
    received_file: Path, tmp_path: Path, settings: Settings
):
    ds = read_dataset(received_file)
    study_uid = ds.StudyInstanceUID
    ds.StudyInstanceUID = "1.2.826.0.1.3680043.2.1125.1"
    other_file = tmp_path / "other.dcm"
    ds.save_as(other_file)

    command = _create_command(settings, 9995)
    # Files nobody takes are deleted right away, which shows that they were handled
    settings.RECEIVER_SPOOL_TTL = 0
    server_task = asyncio.create_task(command._file_transmit.start())
    await asyncio.sleep(0.5)

    subscribed = asyncio.Event()

    async def file_received_handler(filename: str, metadata: Metadata):
        await os.remove(filename)
        return False

    client_task = asyncio.create_task(
        FileTransmitClient(HOST, 9995).subscribe(
            study_uid, file_received_handler, subscribed_handler=subscribed.set
        )
    )
    await asyncio.wait_for(subscribed.wait(), timeout=5)
    resume = stall_session(command._file_transmit._sessions[0])

    send_task = asyncio.create_task(command._send_files())
    try:
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        command._queue.sync_q.put(ReceivedFile(str(other_file), "PACS1"))
        # The file of a study nobody subscribed to is handled meanwhile
        await wait_until(lambda: not other_file.exists())
        assert received_file.exists()

        resume.set()
        await wait_until(lambda: not received_file.exists())
    finally:
        resume.set()
        send_task.cancel()
        client_task.cancel()
        with suppress(asyncio.CancelledError):
            await client_task
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)


@pytest.mark.asyncio
async def test_send_files_deletes_a_file_it_could_not_publish(
    received_file: Path, tmp_path: Path, settings: Settings
):
    second_file = Path(shutil.copy(received_file, tmp_path / "second.dcm"))
    command = _create_command(settings)
    published: list[str] = []

    async def publish_file(topic, file_path, metadata=None, release=None):
        published.append(file_path)
        raise OSError("disk gone")

    command._file_transmit.publish_file = publish_file

    send_task = asyncio.create_task(command._send_files())
    try:
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        command._queue.sync_q.put(ReceivedFile(str(second_file), "PACS1"))
        await wait_until(lambda: not received_file.exists() and not second_file.exists())
    finally:
        send_task.cancel()
        await _close_queue(command)

    assert published == [str(received_file), str(second_file)]


@pytest.mark.asyncio
async def test_release_of_a_file_already_gone_is_silent(
    received_file: Path, tmp_path: Path, settings: Settings, caplog: pytest.LogCaptureFixture
):
    second_file = Path(shutil.copy(received_file, tmp_path / "second.dcm"))
    command = _create_command(settings)
    published: list[str] = []

    async def publish_file(topic, file_path, metadata=None, release=None):
        # The file is gone before a session is done with it, e.g. when the receiver left its
        # temp folder
        published.append(file_path)
        Path(file_path).unlink()
        assert release
        release(True)
        return 1

    command._file_transmit.publish_file = publish_file

    send_task = asyncio.create_task(command._send_files())
    try:
        with caplog.at_level(logging.WARNING):
            command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
            command._queue.sync_q.put(ReceivedFile(str(second_file), "PACS1"))
            await wait_until(lambda: len(published) == 2)
    finally:
        send_task.cancel()
        await _close_queue(command)

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_sync_is_answered_after_the_files_queued_before_it(
    received_file: Path, settings: Settings
):
    study_uid = read_dataset(received_file).StudyInstanceUID
    command = _create_command(settings, 9996)
    server_task = asyncio.create_task(command._file_transmit.start())
    await asyncio.sleep(0.5)

    subscribed = asyncio.Event()
    synced = asyncio.Event()
    events: list[str] = []

    async def file_received_handler(filename: str, metadata: Metadata):
        events.append("file")
        await os.remove(filename)
        return False

    def synced_handler(token: str):
        events.append(f"synced {token}")
        if token == "1":
            synced.set()

    client = FileTransmitClient(HOST, 9996)
    client_task = asyncio.create_task(
        client.subscribe(
            study_uid,
            file_received_handler,
            subscribed_handler=subscribed.set,
            synced_handler=synced_handler,
        )
    )
    await subscribed.wait()

    # The file is queued before the sync request, as a C-STORE before the final C-MOVE response
    command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
    assert await client.request_sync("1")
    await wait_until(lambda: command._queue.async_q.qsize() == 2)

    send_task = asyncio.create_task(command._send_files())
    try:
        await asyncio.wait_for(synced.wait(), timeout=5)
    finally:
        send_task.cancel()
        client_task.cancel()
        with suppress(asyncio.CancelledError):
            await client_task
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)

    # The receiver confirms the replay of its spooled files right after the subscription
    assert events == [f"synced {REPLAY_SYNC_TOKEN}", "file", "synced 1"]


@pytest.mark.asyncio
async def test_sync_request_of_a_closed_session_is_skipped(received_file: Path, settings: Settings):
    closed_session = FileTransmitSession("foobar", MagicMock(), write_timeout=30)
    closed_session.closed = True
    command = _create_command(settings)
    # Files nobody takes are deleted right away, which shows that they were handled
    settings.RECEIVER_SPOOL_TTL = 0

    send_task = asyncio.create_task(command._send_files())
    try:
        command._queue.sync_q.put(SyncRequest(closed_session, "1"))
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        # The dispatcher went on to the file
        await wait_until(lambda: not received_file.exists())
    finally:
        send_task.cancel()
        await _close_queue(command)

    assert closed_session._frames.empty()


async def _subscribe_and_record(
    port: int, study_uid: str, events: list[str], scope: str | None = None
) -> asyncio.Task:
    """Subscribe a worker that records the files and confirmations it gets."""
    subscribed = asyncio.Event()

    async def file_received_handler(filename: str, metadata: Metadata):
        events.append(f"file {metadata['SOPInstanceUID']} from {metadata['CallingAETitle']}")
        await os.remove(filename)
        return False

    client_task = asyncio.create_task(
        FileTransmitClient(HOST, port).subscribe(
            study_uid,
            file_received_handler,
            subscribed_handler=subscribed.set,
            synced_handler=lambda token: events.append(f"synced {token}"),
            scope=scope,
        )
    )
    await asyncio.wait_for(subscribed.wait(), timeout=5)
    return client_task


@pytest.mark.asyncio
async def test_a_subscriber_of_a_series_gets_only_its_files_replayed(
    tmp_path: Path, settings: Settings
):
    # Arrange: files of two series of a study no worker took
    command = _create_command(settings, 9991)
    files: list[Path] = []
    for received_at, series_uid in enumerate(["1.2.3.1", "1.2.3.2"]):
        files.append(tmp_path / series_uid)
        files[-1].write_bytes(bytes(1024))
        metadata = {
            "SOPInstanceUID": f"{series_uid}.1",
            "SeriesInstanceUID": series_uid,
            "CallingAETitle": "PACS1",
        }
        command._spool_file("1.2.3", str(files[-1]), metadata, received_at)
    server_task = asyncio.create_task(command._file_transmit.start())
    await asyncio.sleep(0.5)
    series_events: list[str] = []
    study_events: list[str] = []
    client_tasks: list[asyncio.Task] = []

    # Act: a fetch of the second series subscribes first, then one of the whole study
    try:
        client_tasks.append(await _subscribe_and_record(9991, "1.2.3", series_events, "1.2.3.2"))
        await wait_until(lambda: f"synced {REPLAY_SYNC_TOKEN}" in series_events)
        client_tasks.append(await _subscribe_and_record(9991, "1.2.3", study_events))
        await wait_until(lambda: f"synced {REPLAY_SYNC_TOKEN}" in study_events)
        await wait_until(lambda: not any(file.exists() for file in files))
    finally:
        for client_task in client_tasks:
            client_task.cancel()
            with suppress(asyncio.CancelledError):
                await client_task
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)

    # Assert: the other series was kept for the next fetch
    assert series_events == ["file 1.2.3.2.1 from PACS1", f"synced {REPLAY_SYNC_TOKEN}"]
    assert study_events == ["file 1.2.3.1.1 from PACS1", f"synced {REPLAY_SYNC_TOKEN}"]
    assert command._spool == {}


@pytest.mark.asyncio
async def test_an_undelivered_file_is_replayed_to_the_next_subscriber(
    received_file: Path, settings: Settings
):
    ds = read_dataset(received_file)
    command = _create_command(settings, 9994)
    server_task = asyncio.create_task(command._file_transmit.start())
    await asyncio.sleep(0.5)
    send_task = asyncio.create_task(command._send_files())
    events: list[str] = []
    client_task = None
    try:
        # Received while no worker is subscribed, e.g. while the worker restarts
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        await wait_until(lambda: ds.StudyInstanceUID in command._spool)

        client_task = await _subscribe_and_record(9994, ds.StudyInstanceUID, events)
        await wait_until(lambda: f"synced {REPLAY_SYNC_TOKEN}" in events)
        await wait_until(lambda: not received_file.exists())
    finally:
        send_task.cancel()
        if client_task:
            client_task.cancel()
            with suppress(asyncio.CancelledError):
                await client_task
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)

    # The replayed files come before the confirmation of the replay
    # Still with the AE title it came from, which a worker may check
    assert events == [f"file {ds.SOPInstanceUID} from PACS1", f"synced {REPLAY_SYNC_TOKEN}"]
    assert command._spool == {}
    assert command._spool_size == 0


@pytest.mark.asyncio
async def test_without_a_spool_undelivered_files_are_deleted_and_the_replay_confirmed(
    received_file: Path, settings: Settings
):
    ds = read_dataset(received_file)
    command = _create_command(settings, 9993)
    settings.RECEIVER_SPOOL_TTL = 0
    server_task = asyncio.create_task(command._file_transmit.start())
    await asyncio.sleep(0.5)
    send_task = asyncio.create_task(command._send_files())
    events: list[str] = []
    client_task = None
    try:
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        await wait_until(lambda: not received_file.exists())

        client_task = await _subscribe_and_record(9993, ds.StudyInstanceUID, events)
        await wait_until(lambda: bool(events))
    finally:
        send_task.cancel()
        if client_task:
            client_task.cancel()
            with suppress(asyncio.CancelledError):
                await client_task
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)

    assert events == [f"synced {REPLAY_SYNC_TOKEN}"]
    assert command._spool == {}


@pytest.mark.asyncio
async def test_spooled_files_expire_after_the_ttl(
    received_file: Path, settings: Settings, caplog: pytest.LogCaptureFixture
):
    study_uid = read_dataset(received_file).StudyInstanceUID
    command = _create_command(settings)
    settings.RECEIVER_SPOOL_TTL = 1
    send_task = asyncio.create_task(command._send_files())
    try:
        command._queue.sync_q.put(ReceivedFile(str(received_file), "PACS1"))
        await wait_until(lambda: study_uid in command._spool)

        command._expire_spooled_files()
        assert received_file.exists()

        await asyncio.sleep(1.1)
        with caplog.at_level(logging.INFO):
            command._expire_spooled_files()
    finally:
        send_task.cancel()
        await _close_queue(command)

    assert not received_file.exists()
    assert command._spool == {}
    assert command._spool_size == 0
    assert any(study_uid in r.getMessage() for r in caplog.records if r.levelno == logging.INFO)


def test_the_spool_evicts_the_oldest_files_over_its_size(
    tmp_path: Path, settings: Settings, caplog: pytest.LogCaptureFixture
):
    settings.RECEIVER_SPOOL_MAX_SIZE = 1  # MB
    command = _create_command(settings)
    files = {}
    for name in ["a", "b", "c"]:
        files[name] = tmp_path / name
        files[name].write_bytes(bytes(400 * 1024))
    too_large = tmp_path / "too_large"
    too_large.write_bytes(bytes(1024 * 1024 + 1))

    with caplog.at_level(logging.WARNING):
        for received_at, name in enumerate(["a", "b", "c"]):
            command._spool_file("1.2.3", str(files[name]), {"SOPInstanceUID": name}, received_at)
        command._spool_file("4.5.6", str(too_large), {"SOPInstanceUID": "big"}, 3)
    evicting_warnings = [r for r in caplog.records if r.levelno == logging.WARNING]

    assert not files["a"].exists()
    assert files["b"].exists() and files["c"].exists()
    assert not too_large.exists()
    assert [spooled.metadata["SOPInstanceUID"] for spooled in command._spool["1.2.3"]] == [
        "b",
        "c",
    ]
    assert command._spool_size == 2 * 400 * 1024

    # Reported in one line by the next expiry pass, as a full spool evicts a file for every
    # file it takes
    assert evicting_warnings == []
    with caplog.at_level(logging.WARNING):
        command._expire_spooled_files()
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "discarded the 1 oldest" in warnings[0]


@pytest.mark.asyncio
async def test_shutdown_deletes_the_files_the_receiver_holds(tmp_path: Path, settings: Settings):
    # Arrange: a file in the spool of a running receiver
    command = _create_command(settings)
    command.loop = asyncio.get_running_loop()
    command._store_scp = MagicMock()
    command._folder = tmp_path / "receiver"
    command._folder.mkdir()
    spooled = command._folder / "spooled.dcm"
    spooled.write_bytes(bytes(1024))
    command._spool_file("1.2.3", str(spooled), {"SOPInstanceUID": "1.2.3.4"}, 0)

    # Act: the process ends right after, without leaving the folder's context
    command.on_shutdown()
    await asyncio.sleep(0.1)  # Lets the file transmit server stop

    # Assert
    command._store_scp.stop.assert_called_once()
    assert not command._folder.exists()
