import logging
import threading
from pathlib import Path

from adit_radis_shared.common.management.base.server_command import ServerCommand
from django import db
from django.conf import settings
from django.db import DatabaseError

from adit.core.utils.store_scp import StoreScp

from ...utils import spool
from ...utils.intake import RouterStoreHandler, build_router_scp, load_intake_config

logger = logging.getLogger(__name__)

STARTUP_RETRY_SECONDS = 5


class Command(ServerCommand):
    help = "Starts the DICOM router, a C-STORE SCP that spools the images of registered senders."
    server_name = "DICOM router"
    paths_to_watch = settings.SOURCE_PATHS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stopped = threading.Event()
        self._store_scp: StoreScp | None = None

    def run_server(self, **options):
        if not settings.ROUTER_AE_TITLE:
            self.stdout.write("ROUTER_AE_TITLE is not set, the DICOM router is disabled.")
            self._stopped.wait()
            return

        spool_root = Path(settings.ROUTER_SPOOL_PATH)
        spool.ensure_spool_dirs(spool_root)
        removed = spool.clean_tmp(spool_root)
        if removed:
            logger.warning("Removed %d partly written files from the router spool.", removed)

        handler = RouterStoreHandler(
            spool_root, min_free_bytes=settings.ROUTER_SPOOL_MIN_FREE_GB * 1024**3
        )
        store_scp = build_router_scp(
            spool_root,
            handler,
            ae_title=settings.ROUTER_AE_TITLE,
            host="0.0.0.0",
            port=settings.ROUTER_SCP_PORT,
            debug=settings.ENABLE_DICOM_DEBUG_LOGGER,
        )
        self._store_scp = store_scp

        loaded = self._load_config_until_ready(store_scp, handler)
        # This thread now only waits on the listener, so it gives its connection back.
        db.connection.close()
        if not loaded or self._stopped.is_set():
            return

        threading.Thread(
            target=self._refresh_periodically, args=(store_scp, handler), daemon=True
        ).start()
        store_scp.start()

    def on_shutdown(self):
        self._stopped.set()
        if self._store_scp:
            self._store_scp.stop()

    def _refresh(self, store_scp: StoreScp, handler: RouterStoreHandler) -> None:
        config = load_intake_config()
        handler.update_config(config)
        store_scp.set_allowed_calling_aets(config.sender_ids.keys())

    def _load_config_until_ready(self, store_scp: StoreScp, handler: RouterStoreHandler) -> bool:
        """Retry until the database answers; returns False if the command stops first.

        In development the router can start before the web container has migrated
        the database.
        """
        while not self._stopped.is_set():
            try:
                self._refresh(store_scp, handler)
                return True
            except DatabaseError:
                logger.warning("Router senders could not be loaded yet, retrying.", exc_info=True)
                self._stopped.wait(STARTUP_RETRY_SECONDS)
        return False

    def _refresh_periodically(self, store_scp: StoreScp, handler: RouterStoreHandler) -> None:
        while not self._stopped.wait(settings.ROUTER_SENDER_REFRESH_SECONDS):
            try:
                self._refresh(store_scp, handler)
            except DatabaseError:
                logger.exception("Could not reload the router senders; keeping the last ones.")
            finally:
                db.connection.close()
