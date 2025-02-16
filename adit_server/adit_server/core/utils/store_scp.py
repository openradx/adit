import argparse
import errno
import logging
import os
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable

from pynetdicom import debug_logger, evt
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.events import Event
from pynetdicom.presentation import AllStoragePresentationContexts

from .dicom_utils import write_dataset

logger = logging.getLogger(__name__)

FileReceivedHandler = Callable[[str], None]


class StoreScp:
    _ae: AE | None = None
    _file_received_handler: FileReceivedHandler | None = None

    def __init__(self, folder: os.PathLike, ae_title: str, host: str, port: int, debug=False):
        self._folder = folder
        self._ae_title = ae_title
        self._host = host
        self._port = port
        self._debug = debug
        self._stopped = threading.Event()

    def start(self):
        if self._debug:
            debug_logger()

        exists = os.path.exists(self._folder)
        is_dir = os.path.isdir(self._folder)
        if not exists or not is_dir:
            raise IOError(f"Invalid folder to store DICOM files: {self._folder}")

        self._ae = AE(ae_title=self._ae_title)

        # Speed up by reducing the number of required DIMSE messages
        # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
        self._ae.maximum_pdu_size = 0

        self._ae.supported_contexts = AllStoragePresentationContexts
        handlers = [
            (evt.EVT_CONN_OPEN, self._on_connect),
            (evt.EVT_CONN_CLOSE, self._on_close),
            (evt.EVT_ESTABLISHED, self._on_established),
            (evt.EVT_RELEASED, self._on_released),
            (evt.EVT_ABORTED, self._on_aborted),
            (evt.EVT_C_STORE, self._handle_store),
        ]

        logger.info(
            f"Store SCP server [{self._ae_title}] serving on {self._host or '*'}:{self._port}"
        )

        try:
            self._ae.start_server((self._host, self._port), evt_handlers=handlers, block=False)
            self._stopped.wait()
        finally:
            logger.info("Store SCP server stopped")

    def stop(self):
        if self._ae:
            self._ae.shutdown()
            self._stopped.set()

        self._ae = None

    def set_file_received_handler(self, handler: FileReceivedHandler):
        self._file_received_handler = handler

    def _on_connect(self, event: Event):
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Connection to remote %s:%d opened", address, port)

    def _on_close(self, event: Event):
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Connection to remote %s:%d closed", address, port)

    def _on_established(self, event: Event):
        calling_ae = event.assoc.remote["ae_title"]
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Association to %s [%s:%d] established.", calling_ae, address, port)

    def _on_released(self, event: Event):
        calling_ae = event.assoc.remote["ae_title"]
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Association to %s [%s:%d] released.", calling_ae, address, port)

    def _on_aborted(self, event: Event):
        calling_ae = event.assoc.remote["ae_title"]
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Association to %s [%s:%d] was aborted.", calling_ae, address, port)

    def _handle_store(self, event: Event):
        """Handle a C-STORE request event.

        The request is initiated with a C-MOVE request by ADIT itself to
        fetch images from a DICOM server that doesn't support C-GET requests.
        """
        # We retain the calling AE title in the filename so that we can use it in the
        # transmitter for the topic.
        calling_ae = event.assoc.remote["ae_title"]
        file_prefix = calling_ae + "_"

        try:
            with NamedTemporaryFile(
                prefix=file_prefix, suffix=".dcm", dir=self._folder, delete=False
            ) as file:
                # There are two ways to save the file. We use the first one and prefer
                # reliability over speed. (See file history for second method.)
                # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
                ds = event.dataset
                ds.file_meta = event.file_meta
                write_dataset(ds, file.name)
        except Exception as err:
            if isinstance(err, OSError) and err.errno == errno.ENOSPC:
                logger.error("Out of disc space while saving received file.")
            else:
                logger.error("Unable to write file to disc: %s", err)
            logger.exception(err)

            # We abort the association as don't want to get more images.
            # We can't use C-CANCEL as not all PACS servers support or respect it.
            # See https://github.com/pydicom/pynetdicom/issues/553
            # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
            event.assoc.abort()

            # Answer with "Out of Resources"
            # see https://pydicom.github.io/pynetdicom/stable/service_classes/defined_procedure_service_class.html # noqa: E501
            return 0xA702

        try:
            if self._file_received_handler:
                self._file_received_handler(file.name)
        except Exception as err:
            logger.error("Unable to handle received file %s: %s", file.name, err)
            logger.exception(err)

        return 0x0000  # Return 'Success' status


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--aet", default="ADIT1")
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=11112)
    args = parser.parse_args()

    store_scp = StoreScp(Path(args.dir), args.aet, args.host, args.port)

    try:
        store_scp.start()
    except KeyboardInterrupt:
        store_scp.stop()


if __name__ == "__main__":
    main()
