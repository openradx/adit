import asyncio
from io import BytesIO
from pathlib import Path

import aiofiles
import pytest
from aiofiles import os
from django.conf import settings
from pydicom import dcmread

from adit.core.utils.file_transmit import FileTransmitClient, FileTransmitServer, Metadata

HOST = "127.0.0.1"
PORT = 9999
NUM_TRANSFER_FILES = 5


@pytest.mark.asyncio
async def test_start_transmit_file():
    samples_path = Path(f"{settings.BASE_DIR}/samples/dicoms")
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

    # TODO: not sure if this is needed
    # await asyncio.sleep(0.1)  # wait until server is ready to accept connections

    async with aiofiles.tempfile.TemporaryDirectory() as temp_dir:
        client = FileTransmitClient(HOST, PORT, temp_dir)

        counter = 0

        async def file_received_handler(buffer: BytesIO, metadata: Metadata):
            nonlocal counter

            buffer_size = buffer.getbuffer().nbytes
            file_size = await os.path.getsize(sample_files[counter])
            assert buffer_size == file_size
            assert metadata["filename"] == sample_files[counter].name
            assert dcmread(buffer).SOPInstanceUID == dcmread(sample_files[counter]).SOPInstanceUID

            counter += 1
            return counter == NUM_TRANSFER_FILES

        client_task = asyncio.create_task(client.subscribe("foobar", file_received_handler))

        await asyncio.gather(client_task, server_task)

        assert counter == NUM_TRANSFER_FILES
