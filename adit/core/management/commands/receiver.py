import asyncio
import functools
import logging
import os
import tempfile
from contextlib import suppress
from pathlib import Path

import janus
from adit_radis_shared.common.management.base.server_command import AsyncServerCommand
from django.conf import settings

from ...utils.dicom_utils import read_dataset
from ...utils.file_transmit import FileTransmitServer
from ...utils.store_scp import StoreScp

logger = logging.getLogger(__name__)


class Command(AsyncServerCommand):
    help = (
        "Starts a receiver with a C-STORE SCP for receiving DICOM files and transmits those"
        "files to subscribing workers."
    )
    server_name = "DICOM receiver"
    paths_to_watch = settings.SOURCE_PATHS

    async def run_server_async(self, **options):
        with tempfile.TemporaryDirectory(prefix="adit_receiver_") as tmpdir:
            self.stdout.write(f"Using receiver directory: {tmpdir}")

            # In Docker swarm mode the host "receiver" resolves to a virtual IP address as multiple
            # replicas can be behind a service (each with its own real IP). So the virtual IP
            # forwards the data to those read IPs. But we can't start a server on such an virtual
            # IP inside the container. We could figure out the read hostname / IP or just
            # use 0.0.0.0 to listen on all interfaces (what we do now).
            self._store_scp = StoreScp(
                folder=Path(tmpdir),
                ae_title=settings.RECEIVER_AE_TITLE,
                host="0.0.0.0",
                port=settings.STORE_SCP_PORT,
                debug=settings.ENABLE_DICOM_DEBUG_LOGGER,
            )

            self._queue: janus.Queue[str] = janus.Queue()

            self._file_transmit = self._create_file_transmit()
            self._store_scp.set_file_received_handler(self._handle_received_file)
            store_scp_thread = asyncio.to_thread(self._store_scp.start)

            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._file_transmit.start())
                    tg.create_task(store_scp_thread)
                    tg.create_task(self._send_files())
            except ExceptionGroup as err:
                # Explicitly stop the  Store SCP server as it is running in a separate thread not
                # using asyncio and can't be stopped by the task group using a CancelledError.
                self._store_scp.stop()

                logger.exception(err)

    def _create_file_transmit(self) -> FileTransmitServer:
        return FileTransmitServer(
            "0.0.0.0",
            settings.FILE_TRANSMIT_PORT,
            write_timeout=settings.FILE_TRANSMIT_WRITE_TIMEOUT,
        )

    def _delete_received_file(self, file_path: str) -> None:
        # The temp folder is gone once a failed task ended the server, and an error here would
        # end the sender of the worker's session that released the file.
        with suppress(FileNotFoundError):
            os.unlink(file_path)

    def _handle_received_file(self, file_path):
        self._queue.sync_q.put(file_path)

    async def _send_files(self):
        while True:
            file_path = await self._queue.async_q.get()
            filename = os.path.basename(file_path)

            study_uid = "Unknown"
            series_uid = "Unknown"
            instance_uid = "Unknown"
            try:
                ds = read_dataset(file_path)
                study_uid = ds.StudyInstanceUID
                series_uid = ds.SeriesInstanceUID
                instance_uid = ds.SOPInstanceUID
                # Routed on the StudyInstanceUID only, as the calling AE title of the C-STOREs
                # may differ from the AE title ADIT queried (e.g. PACS clusters or a separate
                # sending AE). SOPInstanceUIDs are globally unique, so workers dedupe on them.
                sent_count = await self._file_transmit.publish_file(
                    study_uid,
                    file_path,
                    {"SOPInstanceUID": instance_uid},
                    # Deleted once every worker it was queued to is done with it
                    release=functools.partial(self._delete_received_file, file_path),
                )
                if not sent_count:
                    # Also happens for late duplicates after the worker got all its images
                    logger.warning(
                        "No worker subscribed to study '%s', discarding received DICOM file "
                        "with SOPInstanceUID '%s'.",
                        study_uid,
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
