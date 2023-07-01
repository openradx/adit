import errno
import logging
import os
import signal
from pathlib import Path
from socketserver import BaseServer
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Callable, cast

from pydicom.filewriter import write_file_meta_info
from pynetdicom import debug_logger, evt
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.dimse_primitives import C_STORE
from pynetdicom.events import Event
from pynetdicom.presentation import AllStoragePresentationContexts

logger = logging.getLogger(__name__)

FileReceivedHandler = Callable[[str], None]


class StoreScp:
    _assoc_server: BaseServer | None = None

    def __init__(self, folder: os.PathLike, ae_title: str, host: str, port: int, debug=False):
        self._folder = folder
        self._ae_title = ae_title
        self._host = host
        self._port = port
        self._debug = debug

    def start(self):
        if self._debug:
            debug_logger()

        exists = os.path.exists(self._folder)
        is_dir = os.path.isdir(self._folder)
        if not exists or not is_dir:
            raise IOError(f"Invalid folder to store DICOM files: {self._folder}")

        ae = AE(ae_title=self._ae_title)

        # Speed up by reducing the number of required DIMSE messages
        # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
        ae.maximum_pdu_size = 0

        ae.supported_contexts = AllStoragePresentationContexts
        handlers = [
            (evt.EVT_CONN_OPEN, self._on_connect),
            (evt.EVT_CONN_CLOSE, self._on_close),
            (evt.EVT_ESTABLISHED, self._on_established),
            (evt.EVT_RELEASED, self._on_released),
            (evt.EVT_ABORTED, self._on_aborted),
            (evt.EVT_C_STORE, self._handle_store),
        ]

        self._assoc_server = ae.start_server(
            (self._host, self._port), evt_handlers=handlers, block=False
        )
        assert self._assoc_server
        self._assoc_server.serve_forever()

    def stop(self):
        assert self._assoc_server
        self._assoc_server.shutdown()

    def set_file_received_handler(self, handler: FileReceivedHandler):
        self._file_received_handler = handler

    def _on_connect(self, event: Event):
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Connection to remote %s:%d opened", address, port)

        assert event.assoc.acceptor.primitive
        called_ae = event.assoc.acceptor.primitive.called_ae_title
        if called_ae != self._ae_title:
            logger.error(f"Invalid called AE title: {called_ae}")
            event.assoc.abort()

    def _on_close(self, event: Event):
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Connection to remote %s:%d closed", address, port)

    def _on_established(self, event: Event):
        calling_ae = event.assoc.remote["ae_title"]
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Assoication to %s [%s:%d] established.", calling_ae, address, port)

    def _on_released(self, event: Event):
        calling_ae = event.assoc.remote["ae_title"]
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Assoication to %s [%s:%d] released.", calling_ae, address, port)

    def _on_aborted(self, event: Event):
        calling_ae = event.assoc.remote["ae_title"]
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Assoication to %s [%s:%d] was aborted.", calling_ae, address, port)

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
                # Write dataset directly to file without re-encoding.
                # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp

                # Write the preamble and prefix
                file.write(b"\x00" * 128)
                file.write(b"DICM")
                # Encode and write the File Meta Information
                write_file_meta_info(file, event.file_meta)  # type: ignore
                # Write the encoded dataset
                request = cast(C_STORE, event.request)
                assert request.DataSet
                file.write(request.DataSet.getvalue())
        except Exception as err:
            if isinstance(err, OSError) and err.errno == errno.ENOSPC:
                logger.error("Out of disc space while saving received file.")
            else:
                logger.error("Unable to write file to disc: %s", err)

            # We abort the association as don't want to get more images.
            # We can't use C-CANCEL as not all PACS servers support or respect it.
            # See https://github.com/pydicom/pynetdicom/issues/553
            # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
            event.assoc.abort()

            # Answer with "Out of Resources"
            # see https://pydicom.github.io/pynetdicom/stable/service_classes/defined_procedure_service_class.html # noqa: E501
            return 0xA702

        self._file_received_handler(file.name)

        return 0x0000  # Return 'Success' status


if __name__ == "__main__":
    store_scp = StoreScp(Path("./temp"), "ADIT", "127.0.0.1", 32323)

    def handle_shutdown(*args):
        store_scp.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    thread = Thread(target=store_scp.start)
    thread.start()
