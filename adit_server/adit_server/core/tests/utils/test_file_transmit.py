import asyncio
from pathlib import Path

import pytest
from aiofiles import os
from django.conf import settings

from adit_server.core.utils.dicom_utils import read_dataset
from adit_server.core.utils.file_transmit import FileTransmitClient, FileTransmitServer, Metadata

HOST = "127.0.0.1"
PORT = 9999
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
