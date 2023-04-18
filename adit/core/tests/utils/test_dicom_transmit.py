import asyncio
from pathlib import Path

import pytest
from django.conf import settings

from adit.core.utils.dicom_transmit import DicomTransmitClient, DicomTransmitServer

HOSTNAME = "127.0.0.1"
PORT = 9999


@pytest.mark.asyncio
async def test_start_transmit_dicom_file():
    async def subscribe_handler(topic: str, server: DicomTransmitServer):
        print("in handler")
        result = Path(f"{settings.BASE_DIR}/samples/dicoms").rglob("*.dcm")
        file1 = list(result)[0]
        print(file1)
        await server.publish_dicom_file("foobar", file1)

    server = DicomTransmitServer(HOSTNAME, PORT)
    server.set_subscribe_handler(lambda topic: subscribe_handler(topic, server))
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)  # Wait until server is ready to accept connections

    client = DicomTransmitClient(HOSTNAME, PORT)
    client_task = asyncio.create_task(client.subscribe("foobar", lambda x: print(x)))

    await asyncio.gather(server_task, client_task)
