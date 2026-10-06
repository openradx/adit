import asyncio
import logging
import shutil
from pathlib import Path

import janus
import pytest
from aiofiles import os
from django.conf import settings

from adit.core.management.commands.receiver import Command
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import FileTransmitClient, FileTransmitServer, Metadata

HOST = "127.0.0.1"
PORT = 9997


@pytest.fixture
def received_file(tmp_path: Path) -> Path:
    sample_file = next(Path(f"{settings.BASE_PATH}/samples/dicoms").rglob("*.dcm"))
    return Path(shutil.copy(sample_file, tmp_path / "received.dcm"))


@pytest.mark.asyncio
async def test_send_files_routes_on_study_instance_uid(received_file: Path):
    study_uid = read_dataset(received_file).StudyInstanceUID

    command = Command()
    command._queue = janus.Queue()
    command._file_transmit = FileTransmitServer(HOST, PORT)
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
    finally:
        send_task.cancel()
        await command._file_transmit.stop()
        await server_task
        command._queue.close()
        await command._queue.wait_closed()

    assert len(received) == 1
    assert not received_file.exists()


@pytest.mark.asyncio
async def test_send_files_warns_when_no_worker_is_subscribed(
    received_file: Path, caplog: pytest.LogCaptureFixture
):
    study_uid = read_dataset(received_file).StudyInstanceUID

    command = Command()
    command._queue = janus.Queue()
    command._file_transmit = FileTransmitServer(HOST, PORT)

    async def wait_until_discarded():
        while received_file.exists():
            await asyncio.sleep(0.05)

    send_task = asyncio.create_task(command._send_files())
    try:
        with caplog.at_level(logging.WARNING):
            command._queue.sync_q.put(str(received_file))
            await asyncio.wait_for(wait_until_discarded(), timeout=5)
    finally:
        send_task.cancel()
        command._queue.close()
        await command._queue.wait_closed()

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert study_uid in warnings[0]
