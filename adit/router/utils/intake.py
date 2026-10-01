"""What the router accepts: senders, intake checks and the C-STORE handler."""

import logging
from dataclasses import dataclass
from pathlib import Path

from pynetdicom.events import Event

from adit.core.utils.presentation_contexts import storage_scp_contexts
from adit.core.utils.store_scp import StoreScp

from ..models import RouterSender, RouterSettings
from . import spool

logger = logging.getLogger(__name__)

STATUS_SUCCESS = 0x0000
STATUS_OUT_OF_RESOURCES = 0xA700
STATUS_CANNOT_UNDERSTAND = 0xC000


@dataclass(frozen=True)
class IntakeConfig:
    sender_ids: dict[str, int]
    suspended: bool


REFUSE_ALL = IntakeConfig(sender_ids={}, suspended=True)


def load_intake_config() -> IntakeConfig:
    # The row is missing between the migration and post_migrate, or once deleted in the admin.
    router_settings = RouterSettings.objects.first()
    if router_settings is None:
        logger.warning("The router settings are missing; intake stays suspended.")
    suspended = router_settings is None or router_settings.suspended
    senders = RouterSender.objects.filter(enabled=True).values_list("calling_ae_title", "pk")
    return IntakeConfig(
        sender_ids={ae_title.strip(): pk for ae_title, pk in senders},
        suspended=suspended,
    )


class RouterStoreHandler:
    """Answers each C-STORE sent to the router and spools the accepted images."""

    def __init__(self, spool_root: Path, min_free_bytes: int) -> None:
        self._spool_root = spool_root
        self._min_free_bytes = min_free_bytes
        self._config = REFUSE_ALL

    @property
    def config(self) -> IntakeConfig:
        return self._config

    def update_config(self, config: IntakeConfig) -> None:
        self._config = config

    def __call__(self, event: Event) -> int:
        config = self._config
        calling_ae = event.assoc.remote["ae_title"].strip()

        sender_id = config.sender_ids.get(calling_ae)
        if sender_id is None:
            # Unknown senders are refused when they associate, so this is a sender
            # that was disabled while its association was open.
            logger.warning("Refusing image from %s: not an enabled router sender.", calling_ae)
            return STATUS_OUT_OF_RESOURCES

        if config.suspended:
            return STATUS_OUT_OF_RESOURCES

        if spool.free_bytes(self._spool_root) < self._min_free_bytes:
            logger.error("Refusing image from %s: the router spool is low on space.", calling_ae)
            return STATUS_OUT_OF_RESOURCES

        ds = event.dataset
        ds.file_meta = event.file_meta
        try:
            spool.store_dataset(self._spool_root, sender_id, ds)
        except spool.InvalidUidError as err:
            logger.warning("Refusing image from %s: %s", calling_ae, err)
            return STATUS_CANNOT_UNDERSTAND
        except OSError:
            logger.exception("Could not spool image from %s.", calling_ae)
            return STATUS_OUT_OF_RESOURCES
        except Exception:
            # Content the router cannot encode is a permanent failure; "out of resources"
            # would make the sender retry it forever.
            logger.exception("Could not encode image from %s.", calling_ae)
            return STATUS_CANNOT_UNDERSTAND

        return STATUS_SUCCESS


def build_router_scp(
    spool_root: Path,
    handler: RouterStoreHandler,
    ae_title: str,
    host: str,
    port: int,
    debug: bool = False,
) -> StoreScp:
    scp = StoreScp(
        folder=spool_root / spool.TMP,
        ae_title=ae_title,
        host=host,
        port=port,
        debug=debug,
        supported_contexts=storage_scp_contexts(),
        require_called_aet=True,
    )
    scp.set_store_handler(handler)
    scp.set_allowed_calling_aets(handler.config.sender_ids.keys())
    return scp
