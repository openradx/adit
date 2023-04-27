import logging
import os
from socketserver import BaseServer
from tempfile import NamedTemporaryFile
from typing import Callable

from pydicom import dcmwrite
from pynetdicom import AE, AllStoragePresentationContexts, debug_logger, evt
from pynetdicom.events import Event

logger = logging.getLogger(__name__)

FileReceivedHandler = Callable[[str], None]


class StoreScp:
    _assoc_server: BaseServer | None = None

    def __init__(self, folder: str, ae_title: str, host: str, port: int, debug=False):
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
        self._assoc_server.serve_forever()

    def stop(self):
        self._assoc_server.shutdown()

    def set_file_received_handler(self, handler: FileReceivedHandler):
        self._file_received_handler = handler

    def _on_connect(self, event: Event):
        address = event.assoc.remote["address"]
        port = event.assoc.remote["port"]
        logger.info("Connection to remote %s:%d opened", address, port)

        called_ae = event.assoc.acceptor.primitive.called_ae_title
        if called_ae != self._ae_title:
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
        ds = event.dataset
        ds.file_meta = event.file_meta

        # TODO: store in receiver folder
        file = NamedTemporaryFile(suffix=".dcm", dir=self._folder, delete=False)
        dcmwrite(file, ds)
        self._file_received_handler(file.name)

        return 0x0000  # Return 'Success' status
