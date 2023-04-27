import asyncio
import logging

import aiofiles
from django.conf import settings
from pydicom import Dataset, dcmread

from ...utils.file_monitor import FileMonitor
from ...utils.file_transmit import FileTransmitServer
from ...utils.store_scp import StoreScp
from ..base.server_command import ServerCommand

logger = logging.getLogger(__name__)


class Command(ServerCommand):
    help = "Starts a C-STORE SCP for receiving DICOM files."
    server_name = "ADIT DICOM C-STORE SCP Receiver"

    def run_server(self, **options):
        asyncio.run(self.run_server_async())

    async def run_server_async(self):
        async with aiofiles.tempfile.TemporaryDirectory(dir=settings.DICOM_DIR) as temp_dir:
            self.stdout.write(f"Using temporary directory: {temp_dir}")

            store_scp = StoreScp(
                folder=temp_dir,
                ae_title=settings.ADIT_AE_TITLE,
                host=settings.STORE_SCP_HOST,
                port=settings.STORE_SCP_PORT,
                debug=settings.DICOM_DEBUG_LOGGER,
            )
            store_scp_thread = asyncio.to_thread(store_scp.start)

            file_monitor = FileMonitor(temp_dir)
            file_transmit = FileTransmitServer(
                settings.FILE_TRANSMIT_HOST, settings.FILE_TRANSMIT_PORT
            )

            async def handle_received_file(file_path):
                ds: Dataset = await asyncio.to_thread(dcmread(file_path))
                study_uid = ds.StudyInstanceUID
                await file_transmit.publish_file(study_uid, file_path)
                return True

            file_monitor.set_file_handler(handle_received_file)

            file_transmit_server_task = asyncio.create_task(file_transmit.start())
            file_monitor_task = asyncio.create_task(file_monitor.start())

            await asyncio.gather(store_scp_thread, file_transmit_server_task, file_monitor_task)

    def on_shutdown(self):
        # CONTROL-C (with sys.exit(0), see server_command.py) cancels the
        # asyncio tasks by itself. So nothing to do here.
        pass
