import asyncio
import json
import logging
import struct
import tempfile
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiofiles import os
from django.conf import settings

from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import (
    SUBSCRIBED_ACK,
    FileTransmitClient,
    FileTransmitServer,
    FileTransmitSession,
    Metadata,
    SyncRequestHandler,
)
from adit.core.utils.testing_helpers import stall_session, wait_until

HOST = "127.0.0.1"
PORT = 9999
OTHER_PORT = 9998
NUM_TRANSFER_FILES = 5
WRITE_TIMEOUT = 30


@pytest.mark.asyncio
async def test_start_transmit_file():
    samples_path = Path(f"{settings.BASE_PATH}/samples/dicoms")
    sample_files = list(samples_path.rglob("*.dcm"))

    server = FileTransmitServer(HOST, PORT, write_timeout=WRITE_TIMEOUT)

    async def subscribe_handler(topic: str):
        for file in sample_files:
            await server.publish_file("foobar", file, {"filename": file.name})

    async def unsubscribe_handler(topic: str):
        print(f"Unsubscribed from {topic}")
        await server.stop()

    server.set_subscribe_handler(subscribe_handler)
    server.set_unsubscribe_handler(unsubscribe_handler)
    server_task = asyncio.create_task(server.start())

    # Make sure transmit server is started
    await asyncio.sleep(0.5)

    client = FileTransmitClient(HOST, PORT)

    counter = 0

    async def file_received_handler(filename: str, metadata: Metadata):
        nonlocal counter

        expected_file_size = await os.path.getsize(sample_files[counter])
        actual_file_size = await os.path.getsize(filename)
        assert actual_file_size == expected_file_size
        assert metadata["filename"] == sample_files[counter].name
        assert (
            read_dataset(filename).SOPInstanceUID
            == read_dataset(sample_files[counter]).SOPInstanceUID
        )

        counter += 1
        return counter == NUM_TRANSFER_FILES

    client_task = asyncio.create_task(client.subscribe("foobar", file_received_handler))

    await asyncio.gather(client_task, server_task)

    assert counter == NUM_TRANSFER_FILES


@pytest.mark.asyncio
async def test_subscribed_handler_is_called_before_first_file():
    sample_file = next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))

    server = FileTransmitServer(HOST, PORT, write_timeout=WRITE_TIMEOUT)

    async def subscribe_handler(topic: str):
        # Publishing right away is the earliest a file can reach the client
        await server.publish_file(topic, sample_file)

    async def unsubscribe_handler(topic: str):
        await server.stop()

    server.set_subscribe_handler(subscribe_handler)
    server.set_unsubscribe_handler(unsubscribe_handler)
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)

    events: list[str] = []

    async def file_received_handler(filename: str, metadata: Metadata):
        events.append("file")
        await os.remove(filename)
        return True

    client = FileTransmitClient(HOST, PORT)
    await client.subscribe(
        "foobar", file_received_handler, subscribed_handler=lambda: events.append("subscribed")
    )
    await server_task

    assert events == ["subscribed", "file"]


@pytest.mark.asyncio
async def test_subscribe_fails_without_acknowledgement():
    async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await reader.readline()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_connection, HOST, PORT)
    subscribed = False

    def subscribed_handler():
        nonlocal subscribed
        subscribed = True

    try:
        client = FileTransmitClient(HOST, PORT)
        with pytest.raises(ConnectionError):
            await client.subscribe(
                "foobar", lambda filename, metadata: True, subscribed_handler=subscribed_handler
            )
    finally:
        server.close()
        await server.wait_closed()

    assert not subscribed


@pytest.mark.asyncio
async def test_subscribe_raises_when_connection_drops_mid_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await reader.readline()
        writer.write(SUBSCRIBED_ACK)
        # Announce 1000 bytes but only send 10 of them before closing
        writer.write(struct.pack("!I", 1000))
        writer.write(b"{}\n")
        writer.write(b"x" * 10)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_connection, HOST, PORT)
    received: list[str] = []

    try:
        client = FileTransmitClient(HOST, PORT)
        with pytest.raises(asyncio.IncompleteReadError):
            await asyncio.wait_for(
                client.subscribe("foobar", lambda filename, metadata: received.append(filename)),
                timeout=5,
            )
    finally:
        server.close()
        await server.wait_closed()

    assert received == []
    # The partially received file must not be left behind (it may contain patient data)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_partial_file_is_removed_when_subscription_is_cancelled_mid_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await reader.readline()
        writer.write(SUBSCRIBED_ACK)
        # Announce 1000 bytes, send 10 of them and keep the connection open
        writer.write(struct.pack("!I", 1000))
        writer.write(b"{}\n")
        writer.write(b"x" * 10)
        await writer.drain()
        await reader.read()
        writer.close()
        await writer.wait_closed()

    async def wait_for_partial_file():
        while not list(tmp_path.iterdir()):
            await asyncio.sleep(0.05)

    server = await asyncio.start_server(handle_connection, HOST, PORT)

    try:
        client = FileTransmitClient(HOST, PORT)
        subscribe_task = asyncio.create_task(
            client.subscribe("foobar", lambda filename, metadata: True)
        )
        await asyncio.wait_for(wait_for_partial_file(), timeout=5)
        subscribe_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await subscribe_task
    finally:
        server.close()
        await server.wait_closed()

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_publish_file_only_reaches_subscribers_of_the_same_server():
    sample_file = next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))

    server = FileTransmitServer(HOST, PORT, write_timeout=WRITE_TIMEOUT)
    other_server = FileTransmitServer(HOST, OTHER_PORT, write_timeout=WRITE_TIMEOUT)
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)

    subscribed = asyncio.Event()
    received: list[str] = []

    async def file_received_handler(filename: str, metadata: Metadata):
        received.append(filename)
        await os.remove(filename)
        return True

    client = FileTransmitClient(HOST, PORT)
    client_task = asyncio.create_task(
        client.subscribe("foobar", file_received_handler, subscribed_handler=subscribed.set)
    )
    await subscribed.wait()

    try:
        assert await other_server.publish_file("foobar", sample_file) == 0
        assert await server.publish_file("barfoo", sample_file) == 0
        assert await server.publish_file("foobar", sample_file) == 1
        await asyncio.wait_for(client_task, timeout=5)
    finally:
        await server.stop()
        await server_task

    assert len(received) == 1


def _sample() -> Path:
    return next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))


def _largest_sample() -> Path:
    samples = Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm")
    return max(samples, key=lambda path: path.stat().st_size)


async def _serve(
    port: int,
    write_timeout: float = WRITE_TIMEOUT,
    sync_request_handler: SyncRequestHandler | None = None,
) -> tuple[FileTransmitServer, asyncio.Task]:
    server = FileTransmitServer(HOST, port, write_timeout=write_timeout)
    server.set_sync_request_handler(sync_request_handler)
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)
    return server, server_task


async def _stop(server: FileTransmitServer, server_task: asyncio.Task, *client_tasks: asyncio.Task):
    for client_task in client_tasks:
        client_task.cancel()
        with suppress(asyncio.CancelledError, ConnectionError, asyncio.IncompleteReadError):
            await client_task
    await server.stop()
    await server_task


async def _subscribe(port: int, topic: str, received: list[str]) -> asyncio.Task:
    """Subscribe a client that records the "name" of every file it gets and keeps going."""
    subscribed = asyncio.Event()

    async def file_received_handler(filename: str, metadata: Metadata):
        received.append(metadata.get("name", ""))
        await os.remove(filename)
        return False

    client_task = asyncio.create_task(
        FileTransmitClient(HOST, port).subscribe(
            topic, file_received_handler, subscribed_handler=subscribed.set
        )
    )
    await asyncio.wait_for(subscribed.wait(), timeout=5)
    return client_task


@pytest.mark.asyncio
async def test_a_stalled_session_delays_no_other_worker():
    server, server_task = await _serve(9950)
    received_a: list[str] = []
    received_b: list[str] = []
    client_a = await _subscribe(9950, "a", received_a)
    client_b = await _subscribe(9950, "b", received_b)
    resume = stall_session(server._sessions[0])
    try:
        for _ in range(3):
            assert await asyncio.wait_for(server.publish_file("a", _largest_sample()), 5) == 1
        assert await asyncio.wait_for(server.publish_file("b", _sample(), {"name": "b"}), 5) == 1

        await wait_until(lambda: received_b == ["b"])
    finally:
        resume.set()
        await _stop(server, server_task, client_a, client_b)


@pytest.mark.asyncio
async def test_publish_file_keeps_sending_to_the_others_when_one_session_fails():
    server, server_task = await _serve(9969)
    first_received: list[str] = []
    second_received: list[str] = []
    released: list[str] = []
    first = await _subscribe(9969, "foobar", first_received)
    second = await _subscribe(9969, "foobar", second_received)
    # The connection of the first subscriber breaks once the frame header was written
    failing_session = server._sessions[0]
    failing_session._writer.drain = MagicMock(side_effect=ConnectionResetError())
    try:
        publish = server.publish_file(
            "foobar", _sample(), {"name": "file"}, release=lambda: released.append("file")
        )
        assert await asyncio.wait_for(publish, 5) == 2

        await wait_until(lambda: second_received == ["file"])
        with pytest.raises((asyncio.IncompleteReadError, ConnectionError)):
            await asyncio.wait_for(first, timeout=5)
        await wait_until(lambda: failing_session not in server._sessions)
        await wait_until(lambda: released == ["file"])
    finally:
        await _stop(server, server_task, first, second)

    assert failing_session.closed
    assert first_received == []


@pytest.mark.asyncio
async def test_publish_file_releases_the_file_after_the_last_session():
    server, server_task = await _serve(9951)
    first_received: list[str] = []
    second_received: list[str] = []
    released: list[str] = []
    first = await _subscribe(9951, "foobar", first_received)
    second = await _subscribe(9951, "foobar", second_received)
    resume = stall_session(server._sessions[1])
    try:
        publish = server.publish_file(
            "foobar", _sample(), {"name": "file"}, release=lambda: released.append("file")
        )
        assert await asyncio.wait_for(publish, 5) == 2
        await wait_until(lambda: first_received == ["file"])
        await asyncio.sleep(0.2)
        assert released == []

        resume.set()
        await wait_until(lambda: second_received == ["file"])
        await wait_until(lambda: released == ["file"])
        await asyncio.sleep(0.2)
        assert released == ["file"]
    finally:
        resume.set()
        await _stop(server, server_task, first, second)


@pytest.mark.asyncio
async def test_publish_file_without_subscriber_releases_right_away():
    server = FileTransmitServer(HOST, 9952, write_timeout=WRITE_TIMEOUT)
    released: list[str] = []

    sent_count = await server.publish_file(
        "nobody", _sample(), release=lambda: released.append("file")
    )

    assert sent_count == 0
    assert released == ["file"]


@pytest.mark.asyncio
async def test_publish_file_of_a_missing_file_queues_nothing():
    server, server_task = await _serve(9968)
    received: list[str] = []
    released: list[str] = []
    client = await _subscribe(9968, "foobar", received)
    try:
        with pytest.raises(FileNotFoundError):
            await server.publish_file(
                "foobar", "missing.dcm", release=lambda: released.append("missing")
            )
        assert not server._sessions[0].closed

        await asyncio.wait_for(server.publish_file("foobar", _sample(), {"name": "file"}), 5)
        await wait_until(lambda: received == ["file"])
    finally:
        await _stop(server, server_task, client)

    assert released == []


@pytest.mark.asyncio
async def test_publish_file_too_large_for_a_frame_queues_nothing(monkeypatch: pytest.MonkeyPatch):
    server, server_task = await _serve(9967)
    released: list[str] = []
    client = await _subscribe(9967, "foobar", [])
    try:

        async def getsize(path):
            return 2**32  # doesn't fit the 4 byte size of a frame

        monkeypatch.setattr("adit.core.utils.file_transmit.os.path.getsize", getsize)
        with pytest.raises(struct.error):
            await server.publish_file("foobar", _sample(), release=lambda: released.append("f"))
        assert not server._sessions[0].closed
    finally:
        await _stop(server, server_task, client)

    assert released == []


@pytest.mark.asyncio
async def test_closing_a_session_releases_its_queued_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    server, server_task = await _serve(9953)
    released: list[str] = []
    client = await _subscribe(9953, "foobar", [])
    resume = stall_session(server._sessions[0])
    try:
        for name in ["1", "2", "3"]:
            publish = server.publish_file(
                "foobar", _largest_sample(), release=lambda name=name: released.append(name)
            )
            assert await asyncio.wait_for(publish, 5) == 1
        # The client has started on the first file when it goes away
        await wait_until(lambda: any(tmp_path.iterdir()))
        client.cancel()
        with suppress(asyncio.CancelledError):
            await client

        await wait_until(lambda: sorted(released) == ["1", "2", "3"])
        await asyncio.sleep(0.2)
        assert sorted(released) == ["1", "2", "3"]
    finally:
        resume.set()
        await _stop(server, server_task)


@pytest.mark.asyncio
async def test_a_worker_that_reads_nothing_is_disconnected_after_the_write_timeout(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    big_file = tmp_path / "big.bin"
    big_file.write_bytes(bytes(32 * 1024 * 1024))  # more than the socket buffers hold
    server, server_task = await _serve(9957, write_timeout=0.5)
    received: list[str] = []
    released: list[str] = []
    # A hung worker: it subscribes and never reads again
    reader, writer = await asyncio.open_connection(HOST, 9957)
    other = None
    try:
        writer.write(b"hung\n")
        await writer.drain()
        assert await reader.readline() == SUBSCRIBED_ACK
        hung_session = server._sessions[0]
        other = await _subscribe(9957, "other", received)

        with caplog.at_level(logging.WARNING):
            publish = server.publish_file("hung", big_file, release=lambda: released.append("big"))
            assert await asyncio.wait_for(publish, 5) == 1
            publish = server.publish_file(
                "other", _sample(), {"name": "small"}, release=lambda: released.append("small")
            )
            assert await asyncio.wait_for(publish, 5) == 1

            await wait_until(lambda: received == ["small"])
            await wait_until(
                lambda: "big" in released and hung_session not in server._sessions, timeout=10
            )
    finally:
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()
        await _stop(server, server_task, *([other] if other else []))

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("hung" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_close_before_start_releases_the_queue():
    # The connection handler closes a session whose subscription ack could not be sent
    session = FileTransmitSession("foobar", MagicMock(), write_timeout=WRITE_TIMEOUT)
    released: list[str] = []
    assert session.queue_frame(b"header", _sample(), lambda: released.append("file"))

    await session.close()

    assert released == ["file"]
    assert session.closed


@pytest.mark.asyncio
async def test_a_worker_that_finishes_with_files_still_queued_ends_quietly(
    caplog: pytest.LogCaptureFixture,
):
    server, server_task = await _serve(9954)
    released: list[str] = []
    subscribed = asyncio.Event()

    async def file_received_handler(filename: str, metadata: Metadata):
        await os.remove(filename)
        return True  # finished after the first file, the others are still queued or in flight

    client = asyncio.create_task(
        FileTransmitClient(HOST, 9954).subscribe(
            "foobar", file_received_handler, subscribed_handler=subscribed.set
        )
    )
    await asyncio.wait_for(subscribed.wait(), timeout=5)
    try:
        with caplog.at_level(logging.WARNING):
            for name in ["1", "2", "3", "4", "5"]:
                publish = server.publish_file(
                    "foobar", _largest_sample(), release=lambda name=name: released.append(name)
                )
                assert await asyncio.wait_for(publish, 5) == 1
            await asyncio.wait_for(client, timeout=5)

            await wait_until(lambda: sorted(released) == ["1", "2", "3", "4", "5"])
            await wait_until(lambda: not server._sessions)
    finally:
        await _stop(server, server_task, client)

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def _answer_right_away(session: FileTransmitSession, token: str):
    session.queue_synced(token)


async def _read_frame(reader: asyncio.StreamReader) -> tuple[int, dict]:
    size = struct.unpack("!I", await reader.readexactly(4))[0]
    return size, json.loads(await reader.readline())


@pytest.mark.asyncio
async def test_sync_request_reaches_the_sync_handler():
    requests: list[tuple[str, str]] = []
    requested = asyncio.Event()

    async def sync_handler(session: FileTransmitSession, token: str):
        requests.append((session.topic, token))
        requested.set()

    server, server_task = await _serve(9979, sync_request_handler=sync_handler)
    subscribed = asyncio.Event()
    client = FileTransmitClient(HOST, 9979)
    client_task = asyncio.create_task(
        client.subscribe(
            "foobar", lambda filename, metadata: True, subscribed_handler=subscribed.set
        )
    )
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=5)
        assert await client.request_sync("1")
        await asyncio.wait_for(requested.wait(), timeout=5)
    finally:
        await _stop(server, server_task, client_task)

    assert requests == [("foobar", "1")]


@pytest.mark.asyncio
async def test_synced_arrives_after_the_files_published_before_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    sample_files = list(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))[:2]
    server, server_task = await _serve(9977)
    subscribed = asyncio.Event()
    synced = asyncio.Event()
    events: list[str] = []

    async def file_received_handler(filename: str, metadata: Metadata):
        events.append(metadata["name"])
        await os.remove(filename)
        return False

    def synced_handler(token: str):
        events.append(f"synced {token}")
        synced.set()

    client = FileTransmitClient(HOST, 9977)
    client_task = asyncio.create_task(
        client.subscribe(
            "foobar",
            file_received_handler,
            subscribed_handler=subscribed.set,
            synced_handler=synced_handler,
        )
    )
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=5)
        await server.publish_file("foobar", sample_files[0], {"name": "first"})
        await server.publish_file("foobar", sample_files[1], {"name": "second"})
        assert server._sessions[0].queue_synced("1")
        await asyncio.wait_for(synced.wait(), timeout=5)
    finally:
        await _stop(server, server_task, client_task)

    assert events == ["first", "second", "synced 1"]
    # A control frame carries no file
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_server_ignores_unknown_and_over_long_control_lines(caplog: pytest.LogCaptureFixture):
    server, server_task = await _serve(9976, sync_request_handler=_answer_right_away)
    reader, writer = await asyncio.open_connection(HOST, 9976)
    try:
        writer.write(b"foobar\n")
        assert await reader.readline() == SUBSCRIBED_ACK
        with caplog.at_level(logging.WARNING):
            writer.write(b"bogus 1\n")
            writer.write(b"x" * (70 * 1024) + b"\n")
            writer.write(b"sync 2\n")
            await writer.drain()
            size, metadata = await asyncio.wait_for(_read_frame(reader), timeout=5)
    finally:
        writer.close()
        await writer.wait_closed()
        await _stop(server, server_task)

    assert (size, metadata) == (0, {"control": "synced", "token": "2"})
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) >= 2


@pytest.mark.asyncio
async def test_session_ends_on_a_partial_control_line():
    server, server_task = await _serve(9975)
    unsubscribed = asyncio.Event()
    server.set_unsubscribe_handler(lambda topic: unsubscribed.set())
    reader, writer = await asyncio.open_connection(HOST, 9975)
    try:
        writer.write(b"foobar\n")
        assert await reader.readline() == SUBSCRIBED_ACK
        writer.write(b"sync 1")
        writer.write_eof()
        await asyncio.wait_for(unsubscribed.wait(), timeout=5)
        # No synced answer for the cut off request
        assert await reader.read() == b""
    finally:
        writer.close()
        await writer.wait_closed()
        await _stop(server, server_task)


@pytest.mark.asyncio
async def test_client_ignores_unknown_control_frames(caplog: pytest.LogCaptureFixture):
    async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await reader.readline()
        writer.write(SUBSCRIBED_ACK)
        writer.write(struct.pack("!I", 0) + b'{"control": "bogus"}\n')
        writer.write(struct.pack("!I", 3) + b'{"name": "file"}\n' + b"abc")
        await writer.drain()
        await reader.read()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_connection, HOST, 9974)
    received: list[str] = []

    async def file_received_handler(filename: str, metadata: Metadata):
        received.append(metadata["name"])
        await os.remove(filename)
        return True

    try:
        with caplog.at_level(logging.WARNING):
            client = FileTransmitClient(HOST, 9974)
            await asyncio.wait_for(client.subscribe("foobar", file_received_handler), timeout=5)
    finally:
        server.close()
        await server.wait_closed()

    assert received == ["file"]
    assert any("bogus" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_client_raises_when_a_metadata_line_is_cut_off():
    async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await reader.readline()
        writer.write(SUBSCRIBED_ACK)
        writer.write(struct.pack("!I", 0) + b'{"control": "syn')
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_connection, HOST, 9973)
    try:
        client = FileTransmitClient(HOST, 9973)
        with pytest.raises(asyncio.IncompleteReadError):
            await asyncio.wait_for(
                client.subscribe("foobar", lambda filename, metadata: True), timeout=5
            )
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_request_sync_after_the_subscription_ended_returns_false():
    sample_file = next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))
    server, server_task = await _serve(9971)
    subscribed = asyncio.Event()

    async def file_received_handler(filename: str, metadata: Metadata):
        await os.remove(filename)
        return True

    client = FileTransmitClient(HOST, 9971)
    client_task = asyncio.create_task(
        client.subscribe("foobar", file_received_handler, subscribed_handler=subscribed.set)
    )
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=5)
        await server.publish_file("foobar", sample_file)
        await asyncio.wait_for(client_task, timeout=5)

        assert await client.request_sync("1") is False
    finally:
        await _stop(server, server_task, client_task)


@pytest.mark.asyncio
async def test_request_sync_returns_false_when_the_connection_broke():
    server, server_task = await _serve(9970)
    subscribed = asyncio.Event()
    client = FileTransmitClient(HOST, 9970)
    client_task = asyncio.create_task(
        client.subscribe(
            "foobar", lambda filename, metadata: True, subscribed_handler=subscribed.set
        )
    )
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=5)
        assert client._writer
        client._writer.drain = MagicMock(side_effect=ConnectionResetError())

        assert await client.request_sync("1") is False
    finally:
        await _stop(server, server_task, client_task)


@pytest.mark.asyncio
async def test_queue_synced_to_a_closed_session_returns_false():
    session = FileTransmitSession("foobar", MagicMock(), write_timeout=WRITE_TIMEOUT)
    session.closed = True

    assert session.queue_synced("1") is False
    assert session._frames.empty()
