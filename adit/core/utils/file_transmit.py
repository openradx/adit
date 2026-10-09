import asyncio
import json
import logging
import struct
from collections.abc import Awaitable, Callable
from contextlib import suppress
from os import PathLike

import aiofiles
from aiofiles import os, tempfile

BUFFER_SIZE = 64 * 1024  # 64kb

SUBSCRIBED_ACK = b"subscribed\n"

SubscribeHandler = Callable[[str], None | Awaitable[None]]
UnsubscribeHandler = Callable[[str], None | Awaitable[None]]
FileSentHandler = Callable[[], None]
SubscribedHandler = Callable[[], None]
SyncedHandler = Callable[[str], None]
SyncRequestHandler = Callable[["FileTransmitSession", str], Awaitable[None]]
Metadata = dict[str, str]
FileReceivedHandler = Callable[[str, Metadata], Awaitable[bool | None] | bool | None]

logger = logging.getLogger(__name__)


# Header bytes, the file to send after them (None for a control frame) and the release of the file
Frame = tuple[bytes, PathLike | str | None, Callable[[], None] | None]


class FileTransmitSession:
    """Each client connection to the server is represented by a session.

    A session has its own queue of frames and one sender task that writes them, so a client that
    reads slowly or not at all only holds up its own files. Besides files, the frames include
    control frames: frames of size 0 whose metadata has a "control" key, e.g. the answer to a
    sync request of the client.
    """

    def __init__(self, topic: str, writer: asyncio.StreamWriter, write_timeout: float):
        self.topic = topic
        self.closed = False
        self._writer = writer
        self._write_timeout = write_timeout
        self._frames: asyncio.Queue[Frame] = asyncio.Queue()
        self._sender: asyncio.Task | None = None

    def start(self) -> None:
        self._sender = asyncio.create_task(self._send_frames())

    def queue_frame(
        self,
        header: bytes,
        file_path: PathLike | str | None = None,
        release: Callable[[], None] | None = None,
    ) -> bool:
        """Queue a frame, the header followed by the file if any, behind the frames before it.

        Returns False if the session is closed. Otherwise `release` is called once the session
        is done with the frame: sent, failed or closed.
        """
        if self.closed:
            return False
        self._frames.put_nowait((header, file_path, release))
        return True

    def queue_synced(self, token: str) -> bool:
        """Queue the answer to a sync request behind the frames queued before it.

        Returns False if the session is closed.
        """
        metadata = {"control": "synced", "token": token}
        return self.queue_frame(struct.pack("!I", 0) + (json.dumps(metadata) + "\n").encode())

    async def close(self) -> None:
        self.closed = True
        if self._sender:
            self._sender.cancel()
        # The cancelled sender takes no further frame, so these are released only here
        while not self._frames.empty():
            _, _, release = self._frames.get_nowait()
            if release:
                release()
        if self._sender:
            await asyncio.wait([self._sender])

    async def _send_frames(self) -> None:
        while True:
            header, file_path, release = await self._frames.get()
            try:
                await self._write_frame(header, file_path)
            except Exception as err:
                # The frame is cut off, so the client can no longer read this stream. Closing
                # the connection makes the connection handler close the session, which releases
                # the frames still queued.
                reason = (
                    f"took no data for {self._write_timeout} s"
                    if isinstance(err, TimeoutError)
                    else repr(err)
                )
                logger.warning(
                    "Disconnecting a subscriber of topic %s, sending failed: %s", self.topic, reason
                )
                self.closed = True
                self._writer.transport.abort()
                return
            finally:
                if release:
                    release()

    async def _write_frame(self, header: bytes, file_path: PathLike | str | None) -> None:
        if file_path is None:
            self._writer.write(header)
            await self._drain()
            return

        async with aiofiles.open(file_path, mode="rb") as file:
            self._writer.write(header)
            await self._drain()
            while chunk := await file.read(BUFFER_SIZE):
                self._writer.write(chunk)
                await self._drain()

    async def _drain(self) -> None:
        # A client that takes no data for this long is regarded as hung
        await asyncio.wait_for(self._writer.drain(), self._write_timeout)


class FileTransmitServer:
    """A file transmit server that can be used to send files to clients.

    Clients can subscribe to a topic and will receive all files that are published
    to this topic.
    """

    _server: asyncio.Server | None = None
    _subscribe_handler: SubscribeHandler | None = None
    _unsubscribe_handler: UnsubscribeHandler | None = None
    _sync_request_handler: SyncRequestHandler | None = None

    def __init__(self, host: str, port: int, write_timeout: float):
        self._host = host
        self._port = port
        self._write_timeout = write_timeout
        self._sessions: list[FileTransmitSession] = []

    def set_subscribe_handler(self, subscribe_handler: SubscribeHandler | None):
        """Called when a client subscribes to a topic."""
        self._subscribe_handler = subscribe_handler

    def set_unsubscribe_handler(self, unsubscribe_handler: UnsubscribeHandler | None):
        """Called when a client unsubscribes from a topic."""
        self._unsubscribe_handler = unsubscribe_handler

    def set_sync_request_handler(self, handler: SyncRequestHandler | None):
        """Called with the session and the token when a client requests a sync.

        The handler answers with `session.queue_synced(token)` once everything that should
        precede the answer was queued to the session.
        """
        self._sync_request_handler = handler

    async def publish_file(
        self,
        topic: str,
        file_path: PathLike | str,
        metadata: dict[str, str] | None = None,
        release: Callable[[], None] | None = None,
    ) -> int:
        """Queues a file to all clients that subscribed to the given topic.

        Returns the number of clients that took the file. `release` is called once all of them
        are done with it (sent, failed or disconnected), right away if none took it. If the file
        can't be framed (e.g. it doesn't exist), the error propagates and nothing is queued.
        """
        file_size = await os.path.getsize(file_path)
        header = struct.pack("!I", file_size) + (json.dumps(metadata or {}) + "\n").encode()

        remaining = 0

        def release_one():
            nonlocal remaining
            assert remaining > 0
            remaining -= 1
            if remaining == 0 and release:
                release()

        # No await from here on: the sessions can't change meanwhile, and no session can be done
        # with the file before all of them are counted.
        taken = 0
        for session in self._sessions:
            if session.topic == topic and session.queue_frame(header, file_path, release_one):
                taken += 1
        remaining = taken
        if not taken and release:
            release()
        return taken

    async def start(self):
        self._server = await asyncio.start_server(self._handle_connection, self._host, self._port)
        logger.info(f"File transmit server serving on {self._host or '*'}:{self._port}")

        async with self._server:
            try:
                await self._server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("File transmit server stopped")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        self._server = None

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        line = await reader.readline()
        topic = line.decode().rstrip()

        session = FileTransmitSession(topic, writer, self._write_timeout)
        self._sessions.append(session)

        try:
            # Files published from now on are queued and only sent once the sender starts, so
            # the ack precedes them. Clients wait for it before triggering anything that
            # publishes files to them.
            writer.write(SUBSCRIBED_ACK)
            await writer.drain()
            session.start()

            if self._subscribe_handler:
                if asyncio.iscoroutinefunction(self._subscribe_handler):
                    await self._subscribe_handler(topic)
                else:
                    self._subscribe_handler(topic)

            # The client sends control lines until it is well served and finished, which it
            # communicates by writing an eof.
            while True:
                try:
                    line = await reader.readline()
                except ValueError:
                    # Longer than the stream limit; the reader stays usable
                    logger.warning("Ignoring an over-long control line on topic %s.", topic)
                    continue
                if not line.endswith(b"\n"):
                    break
                await self._handle_control_line(session, line.decode(errors="replace").strip())
        except Exception as err:
            logger.error(f"Exception occurred on topic {topic}: {err}")
        finally:
            self._sessions.remove(session)
            await session.close()
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

            if self._unsubscribe_handler:
                if asyncio.iscoroutinefunction(self._unsubscribe_handler):
                    await self._unsubscribe_handler(topic)
                else:
                    self._unsubscribe_handler(topic)

    async def _handle_control_line(self, session: FileTransmitSession, line: str) -> None:
        command, _, argument = line.partition(" ")
        if command == "sync" and argument and self._sync_request_handler:
            await self._sync_request_handler(session, argument)
        else:
            logger.warning("Ignoring control line %r on topic %s.", line, session.topic)


class FileTransmitClient:
    """A file transmit client that can be used to receive files from a server."""

    _last_read_at: int | None = None

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._writer: asyncio.StreamWriter | None = None

    async def subscribe(
        self,
        topic: str,
        file_received_handler: FileReceivedHandler,
        subscribed_handler: SubscribedHandler | None = None,
        synced_handler: SyncedHandler | None = None,
    ):
        """Subscribes to a topic and receives all files that are published to this topic.

        The file_received_handler is called for each file that is received. It is passed the
        path to the file received. The handler should process the file, maybe move it to a
        new location or delete it afterward. If the file_received_handler returns True,
        the client will unsubscribe from the topic.
        The subscribed_handler is called once the server has registered the subscription,
        so that files published from then on reach this client.
        The synced_handler is called with the token of each answered `request_sync`, after
        all files the server sent before its answer.
        The filename generator is called when the metadata is received and should return
        the filename to use for the file that is received. If no filename generator is
        set, the filename is randomly generated.
        """
        reader, writer = await asyncio.open_connection(self._host, self._port)

        # Send the topic to the server
        try:
            writer.write(f"{topic}\n".encode())
            await writer.drain()

            ack = await reader.readline()
            if ack != SUBSCRIBED_ACK:
                raise ConnectionError(f"File transmit server did not acknowledge topic {topic}.")

            self._writer = writer
            if subscribed_handler:
                subscribed_handler()

            # And wait for the server to send files regarding this topic
            while True:
                # Receive file size
                data = await reader.readexactly(4)
                file_size = struct.unpack("!I", data)[0]

                # Receive metadata
                metadata_bytes = await reader.readline()
                if not metadata_bytes.endswith(b"\n"):
                    raise asyncio.IncompleteReadError(metadata_bytes, None)
                metadata: Metadata = json.loads(metadata_bytes.decode().strip())

                if control := metadata.get("control"):
                    if control == "synced":
                        if synced_handler:
                            synced_handler(metadata["token"])
                    else:
                        logger.warning("Ignoring unknown control frame %r.", control)
                    continue

                async with tempfile.NamedTemporaryFile(delete=False) as f:
                    try:
                        remaining_bytes = file_size
                        while remaining_bytes > 0:
                            chunk_size = min(remaining_bytes, BUFFER_SIZE)
                            # Raises IncompleteReadError if the server goes away mid-file
                            data = await reader.readexactly(chunk_size)
                            await f.write(data)
                            remaining_bytes -= len(data)
                    except BaseException:
                        # Also on cancellation, as the partial file may contain patient data.
                        # A failing removal must not replace the original error.
                        with suppress(OSError):
                            await os.remove(f.name)  # type: ignore
                        raise

                # The file handler can report that no further files are needed by
                # returning True which stops reading further data from the server.
                finished = (
                    await file_received_handler(f.name, metadata)  # type: ignore
                    if asyncio.iscoroutinefunction(file_received_handler)
                    else file_received_handler(f.name, metadata)  # type: ignore
                )
                if finished:
                    break
        finally:
            # No more sync requests once the connection is being closed
            self._writer = None

            # The client reports that it is well served and doesn't need any further
            # files by writing an eof, then closes the connection.
            try:
                writer.write_eof()
            except OSError:
                pass  # the connection may already be gone
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def request_sync(self, token: str) -> bool:
        """Ask the server to answer with `synced` once it sent everything it holds back.

        Returns False if the request could not be sent, because the subscription ended or the
        connection broke (which the running subscription reports itself).
        """
        if not self._writer:
            return False
        try:
            self._writer.write(f"sync {token}\n".encode())
            await self._writer.drain()
        except (ConnectionError, OSError, RuntimeError) as err:
            logger.debug("Could not send sync request %s: %s", token, err)
            return False
        return True
