import asyncio
import logging
import os
from pathlib import Path

from django.conf import settings
from pydicom import Dataset, dcmread

from ...utils.file_monitor import FileMonitor
from ...utils.file_transmit import FileTransmitServer
from ...utils.store_scp import StoreScp
from ..base.server_command import AsyncServerCommand

logger = logging.getLogger(__name__)


class Command(AsyncServerCommand):
    help = (
        "Starts a receiver with a C-STORE SCP for receiving DICOM files and transmits those."
        "files to subscribing Celery workers."
    )
    server_name = "DICOM receiver"

    async def run_server_async(self):
        # No need for an async path library as we only do it once at startup.
        receiver_dir = Path(settings.TEMP_DICOM_DIR) / "receiver"
        receiver_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"Using receiver directory: {receiver_dir}")

        # In Docker swarm mode the host "receiver" resolves to a virtual IP address as multiple
        # replicas can be behind a service (each with its own real IP). So the virtual IP forwards
        # the data to those read IPs. But we can't start a server on such an virtual IP inside
        # the container. We could figure out the read hostname / IP or just use 0.0.0.0 to
        # listen on all interfaces (what we do now).

        self._store_scp = StoreScp(
            folder=receiver_dir,
            ae_title=settings.ADIT_AE_TITLE,
            host="0.0.0.0",
            port=settings.STORE_SCP_PORT,
            debug=settings.ENABLE_DICOM_DEBUG_LOGGER,
        )
        store_scp_thread = asyncio.to_thread(self._store_scp.start)

        self._file_monitor = FileMonitor(receiver_dir)
        self._file_transmit = FileTransmitServer("0.0.0.0", settings.FILE_TRANSMIT_PORT)

        async def handle_received_file(file_path):
            # The calling AE title is retained by the StoreScp class in the filename so
            # that we can use it for the topic when transmitting the file.
            filename: str = os.path.basename(file_path)
            calling_ae = filename.split("_")[0]

            study_uid = "Unknown"
            series_uid = "Unknown"
            instance_uid = "Unknown"
            try:
                ds: Dataset = await asyncio.to_thread(dcmread, file_path, force=True)
                study_uid = ds.StudyInstanceUID
                series_uid = ds.SeriesInstanceUID
                instance_uid = ds.SOPInstanceUID
                topic = f"{calling_ae}\\{study_uid}\\{series_uid}"
                await self._file_transmit.publish_file(
                    topic, file_path, {"SOPInstanceUID": instance_uid}
                )
            except Exception as err:
                # TODO: Maybe store unreadable files in some special folder for later analysis
                logger.error(
                    f"Error while reading and transmitting received DICOM file '{filename}' with "
                    f"StudyInstanceUID '{study_uid}', SeriesInstanceUID '{series_uid}', "
                    f"SOPInstanceUID '{instance_uid}'."
                )
                logger.exception(err)

            # allow the monitor to delete the file after it has been transmitted
            return True

        self._file_monitor.set_file_handler(handle_received_file)

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(store_scp_thread)
                tg.create_task(self._file_transmit.start())
                tg.create_task(self._file_monitor.start())
        except ExceptionGroup as err:
            # Explicitly stop the  Store SCP server as it is running in a separate thread not
            # using asyncio and can't be stopped by the task group using a CancelledError.
            self._store_scp.stop()

            logger.exception(err)

    def on_shutdown(self):
        self._store_scp.stop()
        asyncio.create_task(self._file_transmit.stop())
        self._file_monitor.stop()
