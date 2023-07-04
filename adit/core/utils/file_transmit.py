import asyncio
import json
import logging
import struct
from io import BytesIO
from os import PathLike
from typing import Awaitable, Callable

import aiofiles
from aiofiles import os

BUFFER_SIZE = 1024

SubscribeHandler = Callable[[str], None | Awaitable[None]]
UnsubscribeHandler = Callable[[str], None | Awaitable[None]]
FileSentHandler = Callable[[], None]
Metadata = dict[str, str]
FileReceivedHandler = Callable[[bytes, Metadata], Awaitable[bool | None] | bool | None]

logger = logging.getLogger(__name__)


class FileTransmitSession:
    """Each client connection to the server is represented by a session."""

    def __init__(self, topic: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.topic = topic
        self._reader = reader
        self._writer = writer

    async def send_file(self, file_path: PathLike, metadata: dict[str, str] | None = None):
        # Send file size
        file_size = await os.path.getsize(file_path)
        data = struct.pack("!I", file_size)  # encodes unsigned int to exactly 4 bytes
        self._writer.write(data)
        await self._writer.drain()

        # Send metadata
        if not metadata:
            metadata = {}
        metadata_bytes = (json.dumps(metadata) + "\n").encode()
        self._writer.write(metadata_bytes)
        await self._writer.drain()

        # Send the file itself
        remaining_bytes = file_size
        async with aiofiles.open(file_path, mode="rb") as file:
            # The client writes an eof if it is well served and doesn't need files anymore
            while remaining_bytes > 0 and not self._reader.at_eof():
                chunk_size = min(remaining_bytes, BUFFER_SIZE)
                chunk = await file.read(chunk_size)
                self._writer.write(chunk)
                await self._writer.drain()
                remaining_bytes -= chunk_size


class FileTransmitServer:
    """A file transmit server that can be used to send files to clients.

    Clients can subscribe to a topic and will receive all files that are published
    to this topic.
    """

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._server = None
        self._subscribe_handler: SubscribeHandler | None = None
        self._unsubscribe_handler: UnsubscribeHandler | None = None
        self._sessions: list[FileTransmitSession] = []

    def set_subscribe_handler(self, subscribe_handler: SubscribeHandler | None):
        """Called when a client subscribes to a topic."""
        self._subscribe_handler = subscribe_handler

    def set_unsubscribe_handler(self, unsubscribe_handler: UnsubscribeHandler | None):
        """Called when a client unsubscribes from a topic."""
        self._unsubscribe_handler = unsubscribe_handler

    async def publish_file(
        self,
        topic: str,
        file_path: PathLike,
        metadata: dict[str, str] | None = None,
    ):
        """Publishes a file to all clients that subscribed to the given topic."""
        for session in self._sessions:
            if session.topic == topic:
                await session.send_file(file_path, metadata)

    async def start(self):
        self._server = await asyncio.start_server(self._handle_connection, self._host, self._port)
        addresses = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        logger.info(f"File transmit server serving on {addresses}")

        async with self._server:
            try:
                await self._server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("File transmit server stopped")

    async def stop(self):
        assert self._server
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
            logger.error(f"Exception occurred on topic {topic}: {err}")
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
    """A file transmit client that can be used to receive files from a server."""

    _last_read_at: int | None = None

    def __init__(self, host: str, port: int, folder: PathLike):
        self._host = host
        self._port = port
        self._folder = folder

    async def subscribe(
        self,
        topic: str,
        file_received_handler: FileReceivedHandler,
    ):
        """Subscribes to a topic and receives all files that are published to this topic.

        The file_received_handler is called for each file that is received. It is passed the
        path to the file received. The handler should process the file, maybe move it to a
        new location or delete it afterward. If the file_received_handler returns True,
        the client will unsubscribe from the topic.
        The filename generator is called when the metadata is received and should return
        the filename to use for the file that is received. If no filename generator is
        set, the filename is randomly generated.
        """
        if not await os.path.exists(self._folder) or not await os.path.isdir(self._folder):
            raise IOError(f"Invalid directory to store received files: {self._folder}")

        reader, writer = await asyncio.open_connection(self._host, self._port)

        # Send the topic to the server
        try:
            writer.write(f"{topic}\n".encode())
            await writer.drain()

            # And wait for the server to send files regarding this topic
            while True:
                # Receive file size
                data = await reader.readexactly(4)
                file_size = struct.unpack("!I", data)[0]

                # Receive metadata
                metadata_bytes = await reader.readline()
                metadata: Metadata = json.loads(metadata_bytes.decode().strip())

                buffer = BytesIO()

                remaining_bytes = file_size

                while remaining_bytes > 0:
                    chunk_size = min(remaining_bytes, BUFFER_SIZE)
                    data = await reader.read(chunk_size)
                    buffer.write(data)
                    remaining_bytes -= len(data)

                # The file handler can report that no further files are needed by
                # returning True which stops reading further data from the server.
                finished = (
                    await file_received_handler(buffer.getvalue(), metadata)
                    if asyncio.iscoroutinefunction(file_received_handler)
                    else file_received_handler(buffer.getvalue(), metadata)
                )
                if finished:
                    break
        finally:
            # The client reports that is well served and doesn't need any  further
            # files by writing an eof.
            writer.write_eof()
