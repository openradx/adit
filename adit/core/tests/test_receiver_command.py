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

from adit.core.management.commands.receiver import Command, SyncRequest
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import FileTransmitClient, FileTransmitSession, Metadata
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
    study_uid = read_dataset(received_file).StudyInstanceUID

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
        command._queue.sync_q.put(str(received_file))
        await asyncio.wait_for(client_task, timeout=5)
        await wait_until(lambda: not received_file.exists())
    finally:
        send_task.cancel()
        await command._file_transmit.stop()
        await server_task
        await _close_queue(command)

    assert len(received) == 1


@pytest.mark.asyncio
async def test_send_files_warns_when_no_worker_is_subscribed(
    received_file: Path, settings: Settings, caplog: pytest.LogCaptureFixture
):
    study_uid = read_dataset(received_file).StudyInstanceUID
    command = _create_command(settings)

    send_task = asyncio.create_task(command._send_files())
    try:
        with caplog.at_level(logging.WARNING):
            command._queue.sync_q.put(str(received_file))
            await wait_until(lambda: not received_file.exists())
    finally:
        send_task.cancel()
        await _close_queue(command)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert study_uid in warnings[0]
    assert "No worker subscribed" in warnings[0]


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
        command._queue.sync_q.put(str(received_file))
        command._queue.sync_q.put(str(other_file))
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
        command._queue.sync_q.put(str(received_file))
        command._queue.sync_q.put(str(second_file))
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
        release()
        return 1

    command._file_transmit.publish_file = publish_file

    send_task = asyncio.create_task(command._send_files())
    try:
        with caplog.at_level(logging.WARNING):
            command._queue.sync_q.put(str(received_file))
            command._queue.sync_q.put(str(second_file))
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
    command._queue.sync_q.put(str(received_file))
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

    assert events == ["file", "synced 1"]


@pytest.mark.asyncio
async def test_sync_request_of_a_closed_session_is_skipped(received_file: Path, settings: Settings):
    closed_session = FileTransmitSession("foobar", MagicMock(), write_timeout=30)
    closed_session.closed = True
    command = _create_command(settings)

    send_task = asyncio.create_task(command._send_files())
    try:
        command._queue.sync_q.put(SyncRequest(closed_session, "1"))
        command._queue.sync_q.put(str(received_file))
        # The dispatcher went on to the file
        await wait_until(lambda: not received_file.exists())
    finally:
        send_task.cancel()
        await _close_queue(command)

    assert closed_session._frames.empty()
