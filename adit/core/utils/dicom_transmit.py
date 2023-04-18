import asyncio
import struct
from pathlib import Path
from typing import Callable

import aiofiles
from aiofiles import os

BUFFER_SIZE = 1024


class DicomTransmitSession:
    def __init__(self, topic: str, writer: asyncio.StreamWriter):
        self.topic = topic
        self._writer = writer

    async def send_dicom_file(self, filepath: str):
        file_size = await os.path.getsize(filepath)
        print(f"sending file with size {file_size}")
        data = struct.pack("!I", file_size)
        self._writer.write(data)
        await self._writer.drain()

        remaining_bytes = file_size
        async with aiofiles.open(filepath, mode="rb") as file:
            while remaining_bytes > 0:
                chunk_size = min(remaining_bytes, BUFFER_SIZE)
                chunk = await file.read(chunk_size)
                self._writer.write(chunk)
                await self._writer.drain()
                remaining_bytes -= chunk_size


class DicomTransmitServer:
    def __init__(self, hostname: str, port: int):
        self._hostname = hostname
        self._port = port
        self._subscribe_handler = None
        self._unsubscribe_handler = None
        self._sessions: [DicomTransmitSession] = []

    def set_subscribe_handler(self, subscribe_handler: Callable[[str], None]):
        self._subscribe_handler = subscribe_handler

    def set_unsubscribe_handler(self, unsubscribe_handler: Callable[[str], None]):
        self._unsubscribe_handler = unsubscribe_handler

    async def publish_dicom_file(self, topic: str, dicom_filepath: Path):
        print("publish")
        for session in self._sessions:
            if session.topic == topic:
                await session.send_dicom_file(dicom_filepath)

    async def start(self):
        server = await asyncio.start_server(self._handle_connection, self._hostname, self._port)
        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        print(f"Serving on {addrs}")

        async with server:
            await server.serve_forever()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        line = await reader.readline()
        topic = line.decode().rstrip()
        print(f"New subscription to topic: {topic}")

        session = DicomTransmitSession(topic, writer)
        self._sessions.append(session)

        if self._subscribe_handler:
            await self._subscribe_handler(topic)

        while True:
            data = await reader.read()
            if not data:
                break

        print(f"Client disconnected with topic: {topic}")
        self._sessions.remove(session)


class DicomTransmitClient:
    def __init__(self, hostname: str, port: int):
        self._hostname = hostname
        self._port = port

    async def subscribe(self, topic: str, dicom_file_handler: Callable[[str], None]):
        reader, writer = await asyncio.open_connection(self._hostname, self._port)

        print(f"Subscribing with topic: {topic}")
        writer.write(f"{topic}\n".encode())
        await writer.drain()

        while True:
            data = await reader.readexactly(4)
            file_size = struct.unpack("!I", data)[0]
            print(f"Received file size: {file_size}")

            remaining_bytes = file_size
            async with aiofiles.tempfile.NamedTemporaryFile("wb+", delete=False) as file:
                print(f"Creating file {file.name}")
                while remaining_bytes > 0:
                    chunk_size = min(remaining_bytes, BUFFER_SIZE)
                    data = await reader.read(chunk_size)
                    await file.write(data)
                    remaining_bytes -= len(data)

            disconnect = await dicom_file_handler(file.name)
            if disconnect:
                break

        writer.close()
        await writer.wait_closed()
