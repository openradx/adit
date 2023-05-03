import asyncio
from pathlib import Path

import aiofiles
import pytest
from django.conf import settings

from adit.core.utils.file_transmit import FileTransmitClient, FileTransmitServer

HOST = "127.0.0.1"
PORT = 9999


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

    await asyncio.sleep(0.1)  # wait until server is ready to accept connections

    async with aiofiles.tempfile.TemporaryDirectory() as temp_dir:
        client = FileTransmitClient(HOST, PORT, temp_dir)

        def filename_generator(metadata: dict[str, str]):
            return metadata["filename"]

        async def file_received_handler(filepath: str):
            print(f"we have it {filepath}")
            return True

        client_task = asyncio.create_task(
            client.subscribe("foobar", file_received_handler, filename_generator)
        )

        await asyncio.gather(client_task, server_task)
