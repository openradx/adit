import asyncio
import bisect
import functools
import logging
import os
import shutil
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import janus
from adit_radis_shared.common.management.base.server_command import AsyncServerCommand
from django.conf import settings

from ...utils.dicom_utils import read_dataset
from ...utils.file_transmit import (
    REPLAY_SYNC_TOKEN,
    FileTransmitServer,
    FileTransmitSession,
    Metadata,
    file_frame_header,
)
from ...utils.store_scp import StoreScp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReceivedFile:
    """A file the Store SCP received, with the AE title the C-STORE came from."""

    path: str
    calling_ae_title: str


@dataclass(frozen=True)
class SyncRequest:
    """A worker's request to confirm that everything received before it was sent to it."""

    session: FileTransmitSession
    token: str


@dataclass(frozen=True)
class SpooledFile:
    """A received file no worker took, kept for the next worker that subscribes to its study."""

    path: str
    metadata: Metadata
    received_at: float
    size: int


# How often the receiver deletes spooled files older than RECEIVER_SPOOL_TTL
SPOOL_EXPIRY_INTERVAL = 10  # seconds


class Command(AsyncServerCommand):
    help = (
        "Starts a receiver with a C-STORE SCP for receiving DICOM files and transmits those"
        "files to subscribing workers."
    )
    server_name = "DICOM receiver"
    paths_to_watch = settings.SOURCE_PATHS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The spooled files of each study, oldest first, and their total size in bytes
        self._spool: dict[str, list[SpooledFile]] = {}
        self._spool_size = 0

    async def run_server_async(self, **options):
        with tempfile.TemporaryDirectory(prefix="adit_receiver_") as tmpdir:
            self.stdout.write(f"Using receiver directory: {tmpdir}")
            self._folder = Path(tmpdir)

            # In Docker swarm mode the host "receiver" resolves to a virtual IP address as multiple
            # replicas can be behind a service (each with its own real IP). So the virtual IP
            # forwards the data to those read IPs. But we can't start a server on such an virtual
            # IP inside the container. We could figure out the read hostname / IP or just
            # use 0.0.0.0 to listen on all interfaces (what we do now).
            self._store_scp = StoreScp(
                folder=self._folder,
                ae_title=settings.RECEIVER_AE_TITLE,
                host="0.0.0.0",
                port=settings.STORE_SCP_PORT,
                debug=settings.ENABLE_DICOM_DEBUG_LOGGER,
            )

            self._queue: janus.Queue[ReceivedFile | SyncRequest] = janus.Queue()

            self._file_transmit = self._create_file_transmit()
            self._store_scp.set_file_received_handler(self._handle_received_file)
            store_scp_thread = asyncio.to_thread(self._store_scp.start)

            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._file_transmit.start())
                    tg.create_task(store_scp_thread)
                    tg.create_task(self._send_files())
                    tg.create_task(self._expire_spooled_files_periodically())
            except ExceptionGroup as err:
                # Explicitly stop the  Store SCP server as it is running in a separate thread not
                # using asyncio and can't be stopped by the task group using a CancelledError.
                self._store_scp.stop()

                logger.exception(err)

    def _create_file_transmit(self) -> FileTransmitServer:
        file_transmit = FileTransmitServer(
            "0.0.0.0",
            settings.FILE_TRANSMIT_PORT,
            write_timeout=settings.FILE_TRANSMIT_WRITE_TIMEOUT,
        )
        file_transmit.set_sync_request_handler(self._handle_sync)
        file_transmit.set_subscribe_handler(self._replay_spooled_files)
        return file_transmit

    def _delete_received_file(self, file_path: str) -> None:
        # The temp folder is gone once a failed task ended the server, and an error here would
        # end the sender of the worker's session that released the file.
        with suppress(FileNotFoundError):
            os.unlink(file_path)

    def _release_received_file(
        self,
        study_uid: str,
        file_path: str,
        metadata: Metadata,
        received_at: float,
        delivered: bool,
    ) -> None:
        if delivered:
            self._delete_received_file(file_path)
        else:
            self._spool_file(study_uid, file_path, metadata, received_at)

    def _spool_file(
        self, study_uid: str, file_path: str, metadata: Metadata, received_at: float
    ) -> None:
        max_size = settings.RECEIVER_SPOOL_MAX_SIZE * 1024 * 1024
        try:
            size = os.path.getsize(file_path)
        except FileNotFoundError:
            return  # The temp folder is gone once a failed task ended the server
        if not settings.RECEIVER_SPOOL_TTL or size > max_size:
            self._delete_received_file(file_path)
            return

        # A replayed file nobody took either goes back to its place
        bisect.insort(
            self._spool.setdefault(study_uid, []),
            SpooledFile(file_path, metadata, received_at, size),
            key=lambda spooled: spooled.received_at,
        )
        self._spool_size += size
        while self._spool_size > max_size:
            oldest_study = min(self._spool, key=lambda study: self._spool[study][0].received_at)
            self._unspool(oldest_study, self._spool[oldest_study][0])
            logger.warning(
                "The receiver's spool is full, discarding the oldest file of study '%s'.",
                oldest_study,
            )

    def _unspool(self, study_uid: str, spooled: SpooledFile, delete: bool = True) -> None:
        self._spool[study_uid].remove(spooled)
        if not self._spool[study_uid]:
            del self._spool[study_uid]
        self._spool_size -= spooled.size
        if delete:
            self._delete_received_file(spooled.path)

    def _replay_spooled_files(self, session: FileTransmitSession) -> None:
        # Not a coroutine, so no file can be spooled for the study meanwhile
        for spooled in list(self._spool.get(session.topic, [])):
            # A fetch of one series would skip the others, which are kept for the next fetch
            if session.scope and spooled.metadata.get("SeriesInstanceUID") != session.scope:
                continue
            self._unspool(session.topic, spooled, delete=False)
            release = functools.partial(
                self._release_received_file,
                session.topic,
                spooled.path,
                spooled.metadata,
                spooled.received_at,
            )
            header = file_frame_header(spooled.size, spooled.metadata)
            if not session.queue_frame(header, spooled.path, release):
                release(False)
        # Always confirmed, so a worker can rely on it
        session.queue_synced(REPLAY_SYNC_TOKEN)

    def _expire_spooled_files(self) -> None:
        expired_before = time.monotonic() - settings.RECEIVER_SPOOL_TTL
        for study_uid, files in list(self._spool.items()):
            expired = [spooled for spooled in files if spooled.received_at < expired_before]
            for spooled in expired:
                self._unspool(study_uid, spooled)
            if expired:
                logger.info(
                    "Discarded %d files of study '%s' no worker took within %d s.",
                    len(expired),
                    study_uid,
                    settings.RECEIVER_SPOOL_TTL,
                )

    async def _expire_spooled_files_periodically(self) -> None:
        while True:
            await asyncio.sleep(SPOOL_EXPIRY_INTERVAL)
            self._expire_spooled_files()

    def _handle_received_file(self, file_path: str, calling_ae_title: str):
        # Queued before the Store SCP answers the C-STORE, so the final C-MOVE response of a
        # compliant PACS, and with it the worker's sync request, come after the file.
        self._queue.sync_q.put(ReceivedFile(file_path, calling_ae_title))

    async def _handle_sync(self, session: FileTransmitSession, token: str):
        # Behind the files queued so far, so the answer follows them on the session's stream
        await self._queue.async_q.put(SyncRequest(session, token))

    async def _send_files(self):
        while True:
            item = await self._queue.async_q.get()

            if isinstance(item, SyncRequest):
                # A closed session takes nothing, so there is nobody to answer
                item.session.queue_synced(item.token)
                continue

            file_path = item.path
            filename = os.path.basename(file_path)

            study_uid = "Unknown"
            series_uid = "Unknown"
            instance_uid = "Unknown"
            try:
                ds = read_dataset(file_path)
                received_at = time.monotonic()
                study_uid = ds.StudyInstanceUID
                series_uid = ds.SeriesInstanceUID
                instance_uid = ds.SOPInstanceUID
                # Routed on the StudyInstanceUID only, as the calling AE title of the C-STOREs
                # may differ from the AE title ADIT queried (e.g. PACS clusters or a separate
                # sending AE). SOPInstanceUIDs are globally unique, so workers dedupe on them.
                # The series lets a worker that fetches one series skip the others, the calling
                # AE title one whose server accepts only some.
                metadata = {
                    "SOPInstanceUID": instance_uid,
                    "SeriesInstanceUID": series_uid,
                    "CallingAETitle": item.calling_ae_title,
                }
                sent_count = await self._file_transmit.publish_file(
                    study_uid,
                    file_path,
                    metadata,
                    # Once every worker it was queued to is done with it, deleted if one of them
                    # got it, otherwise spooled
                    release=functools.partial(
                        self._release_received_file, study_uid, file_path, metadata, received_at
                    ),
                )
                if not sent_count:
                    # Also happens for late duplicates after the worker got all its images
                    spooled = self._spool.get(study_uid)
                    # If kept, it is the study's newest spooled file
                    kept = bool(spooled) and spooled[-1].path == file_path
                    logger.warning(
                        "No worker subscribed to study '%s', %s received DICOM file with "
                        "SOPInstanceUID '%s'.",
                        study_uid,
                        f"keeping for {settings.RECEIVER_SPOOL_TTL} s the"
                        if kept
                        else "discarding",
                        instance_uid,
                    )

            except Exception as err:
                # TODO: Maybe store unreadable files in some special folder for later analysis
                logger.error(
                    f"Error while reading and transmitting received DICOM file '{filename}' "
                    f"with StudyInstanceUID '{study_uid}', SeriesInstanceUID '{series_uid}', "
                    f"SOPInstanceUID '{instance_uid}'."
                )
                logger.exception(err)
                self._delete_received_file(file_path)

    def on_shutdown(self):
        self._store_scp.stop()
        asyncio.run_coroutine_threadsafe(self._file_transmit.stop(), self.loop)
        # The process ends right after, without leaving the folder's context, and the images
        # it still holds (above all the spool) must not stay behind in the stopped container
        shutil.rmtree(self._folder, ignore_errors=True)
