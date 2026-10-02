import asyncio
import struct
from os import PathLike
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
)

HOST = "127.0.0.1"
PORT = 9999
OTHER_PORT = 9998
NUM_TRANSFER_FILES = 5


@pytest.mark.asyncio
async def test_start_transmit_file():
    samples_path = Path(f"{settings.BASE_PATH}/samples/dicoms")
    sample_files = list(samples_path.rglob("*.dcm"))

    server = FileTransmitServer(HOST, PORT)

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

    server = FileTransmitServer(HOST, PORT)

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
async def test_subscribe_raises_when_connection_drops_mid_file():
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


@pytest.mark.asyncio
async def test_publish_file_only_reaches_subscribers_of_the_same_server():
    sample_file = next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))

    server = FileTransmitServer(HOST, PORT)
    other_server = FileTransmitServer(HOST, OTHER_PORT)
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


class _RecordingSession(FileTransmitSession):
    def __init__(self, name: str, topic: str, delivered: list[str]):
        super().__init__(topic, MagicMock(), MagicMock())
        self.name = name
        self.delivered = delivered
        self.on_send = lambda: None

    async def send_file(self, file_path: PathLike | str, metadata: dict[str, str] | None = None):
        self.on_send()
        self.delivered.append(self.name)


@pytest.mark.asyncio
async def test_publish_file_reaches_all_subscribers_when_one_disconnects_meanwhile():
    server = FileTransmitServer(HOST, PORT)
    delivered: list[str] = []
    first = _RecordingSession("first", "foobar", delivered)
    second = _RecordingSession("second", "foobar", delivered)
    # The connection handler removes a session when its client goes away, which can happen
    # while a file is being sent to it.
    first.on_send = lambda: server._sessions.remove(first)
    server._sessions.extend([first, second])

    sent_count = await server.publish_file("foobar", "unused.dcm")

    assert delivered == ["first", "second"]
    assert sent_count == 2
