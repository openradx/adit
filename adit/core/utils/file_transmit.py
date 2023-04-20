import asyncio
import struct
from pathlib import Path
from typing import Awaitable, Callable

import aiofiles
from aiofiles import os

BUFFER_SIZE = 1024

SubscribeHandler = Callable[[str], None | Awaitable[None]]
UnsubscribeHandler = Callable[[str], None | Awaitable[None]]
FileSentHandler = Callable[[], None]
FileReceivedHandler = Callable[[str], Awaitable[bool] | bool]


class FileTransmitSession:
    def __init__(self, topic: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.topic = topic
        self._reader = reader
        self._writer = writer

    async def send_file(self, filepath: str, file_sent_handler: FileSentHandler | None):
        file_size = await os.path.getsize(filepath)
        data = struct.pack("!I", file_size)
        self._writer.write(data)
        await self._writer.drain()

        remaining_bytes = file_size
        async with aiofiles.open(filepath, mode="rb") as file:
            # The client writes an eof if it is well served and doesn't need files anymore
            while remaining_bytes > 0 and not self._reader.at_eof():
                chunk_size = min(remaining_bytes, BUFFER_SIZE)
                chunk = await file.read(chunk_size)
                self._writer.write(chunk)
                await self._writer.drain()
                remaining_bytes -= chunk_size

        if file_sent_handler and remaining_bytes == 0:
            file_sent_handler()


class FileTransmitServer:
    def __init__(self, hostname: str, port: int):
        self._hostname = hostname
        self._port = port
        self._server = None
        self._subscribe_handler = None
        self._unsubscribe_handler = None
        self._sessions: [FileTransmitSession] = []

    def set_subscribe_handler(self, subscribe_handler: SubscribeHandler):
        self._subscribe_handler = subscribe_handler

    def set_unsubscribe_handler(self, unsubscribe_handler: UnsubscribeHandler):
        self._unsubscribe_handler = unsubscribe_handler

    async def publish_file(
        self, topic: str, filepath: Path, file_sent_handler: FileSentHandler | None = None
    ):
        for session in self._sessions:
            if session.topic == topic:
                await session.send_file(filepath, file_sent_handler)

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_connection, self._hostname, self._port
        )
        addresses = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        print(f"File transmit server serving on {addresses}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        self._server.close()
        await self._server.wait_closed()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        line = await reader.readline()
        topic = line.decode().rstrip()

        session = FileTransmitSession(topic, reader, writer)
        self._sessions.append(session)

        try:
            if self._subscribe_handler:
                if asyncio.iscoroutinefunction(self._subscribe_handler):
                    await self._subscribe_handler(topic)
                else:
                    self._subscribe_handler(topic)

            while True:
                # The client communicates that it is well served and finished
                # by writing an eof that we check for here
                data = await reader.read()
                if not data and reader.at_eof():
                    break
        except Exception as err:
            print(f"Exception occurred on topic {topic}: {err}")
        finally:
            self._sessions.remove(session)
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

            if self._unsubscribe_handler:
                if asyncio.iscoroutinefunction(self._unsubscribe_handler):
                    await self._unsubscribe_handler(topic)
                else:
                    self._unsubscribe_handler(topic)


class FileTransmitClient:
    def __init__(self, hostname: str, port: int):
        self._hostname = hostname
        self._port = port

    async def subscribe(self, topic: str, file_received_handler: FileReceivedHandler):
        reader, writer = await asyncio.open_connection(self._hostname, self._port)

        # Send the topic to the server
        writer.write(f"{topic}\n".encode())
        await writer.drain()

        # And wait for the server to send files regarding this topic
        while True:
            data = await reader.readexactly(4)
            file_size = struct.unpack("!I", data)[0]

            remaining_bytes = file_size
            async with aiofiles.tempfile.NamedTemporaryFile("wb+", delete=False) as file:
                while remaining_bytes > 0:
                    chunk_size = min(remaining_bytes, BUFFER_SIZE)
                    data = await reader.read(chunk_size)
                    await file.write(data)
                    remaining_bytes -= len(data)

            # The file handler can report that no further files are needed by
            # returning True
            finished = (
                await file_received_handler(file.name)
                if asyncio.iscoroutinefunction(file_received_handler)
                else file_received_handler(file.name)
            )
            if finished:
                break

        # The client reports that is well served and doesn't need any  further
        # files by writing an eof.
        writer.write_eof()
