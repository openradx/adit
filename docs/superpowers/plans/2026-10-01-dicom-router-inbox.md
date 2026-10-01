# DICOM Router Inbox (Stage 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `router` container that accepts C-STORE from registered senders on its own AE title
and port, and writes every image durably into a spool, ready for the rules and delivery of
stage 3.

**Architecture:** A new Django app, `adit/router/`, holds three things:
- the `RouterSender` and `RouterSettings` models;
- the spool module, which writes atomic, fsynced files into
  `incoming/<sender id>/<StudyInstanceUID>/`;
- the intake, whose `RouterStoreHandler` decides the status of each C-STORE.

The existing `StoreScp` gains a calling-AE allow-list, a pluggable store handler and
configurable presentation contexts. `./manage.py router` wires these together and reloads the
senders from the database every 30 s. Nothing reads the spool yet; stage 3 adds closing, rules
and delivery.

**Tech Stack:** Django 6.1, pynetdicom 3.0, pydicom 3.0, pytest with pytest-django, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-30-dicom-router-design.md`. This plan implements stage
2 of §10: §3.1, the `RouterSender` and `RouterSettings` parts of §5.1, and the stage 2 parts of
§7. The router PRs form a stack on main: stage 1 (`2026-10-01-dicom-router-filters.md`) comes
first, and this one stacks on it. Nothing here uses stage 1's code. Stages 3 and 4 get their
own plans after this one.

## Global Constraints

- **Code style:** Google Python style, ruff line length 100, pyright in basic mode.
  - Comments only where the code can't speak for itself, and they explain why.
  - No history in comments or docstrings.
- **Django fields:** a CharField uses `blank=True` (never `null=True`), plus `default=""` when
  it has no initial value. Other fields use `blank=True, null=True`.
- **Invariants:** use `assert` for internal invariants. ADIT never runs with `python -O`.
- **Spool layout:** under `ROUTER_SPOOL_PATH` (default `/spool`), all on one filesystem:
  - `tmp/`
  - `incoming/<sender id>/<StudyInstanceUID>/<SOPInstanceUID>.dcm`
  - `batches/`
  - `quarantine/`
- **Sender id:** `<sender id>` is the `RouterSender` primary key, never the AE title.
- **C-STORE statuses:**
  - `0x0000`: success.
  - `0xA700`: refused because the router is suspended, the spool has less free space than
    `ROUTER_SPOOL_MIN_FREE_GB`, writing failed, or the sender is not enabled.
  - `0xC000`: StudyInstanceUID or SOPInstanceUID is missing, longer than 64 characters, or
    doesn't match `^[0-9]+(\.[0-9]+)*$`.
- **Durability:** success is answered only after the image file and its folder entry have been
  fsynced.
- **Disabled router:** an empty `ROUTER_AE_TITLE` disables the router; the command idles without
  binding a port.
- **Associations:**
  - With no enabled sender, every association is refused.
  - Unknown calling AE titles are rejected.
  - The called AE title must equal `ROUTER_AE_TITLE`.
- **Ports and AE title:**
  - 11112 inside the router container, 11123 on the dev host, `${ROUTER_PORT:-11113}` in
    production.
  - The example AE title is `ADIT1DEVROUTER`.
- **Defaults:** `ROUTER_SENDER_REFRESH_SECONDS=30`, `ROUTER_SPOOL_MIN_FREE_GB=20`.
- **Receiver:** its behaviour must not change. Every new `StoreScp` option defaults to today's
  behaviour.
- **Docs in this PR:** keep `CLAUDE.md`, `example.env` and `docs/user-docs/admin-guide.md` in
  sync.
- **Branch:** `feat/dicom-router-inbox`, stacked on `feat/dicom-router-filters` (stage 1). If
  stage 1 gained commits after this branch was created, rebase onto it before Task 1:
  `git rebase feat/dicom-router-filters`.
- **Running tests and lint:**
  - Tests run in the web container. Start the dev stack with `uv run cli compose-up -- --watch`
    so host edits sync into the containers, then run `uv run cli test -- <paths>`.
  - Lint runs on the host with `uv run cli lint`.
  - `$COMPOSE` below means `docker compose -f docker-compose.base.yml -f docker-compose.dev.yml -p adit_dev`.
  - If `docker compose exec` output gets cut off, write the command's output to a file inside
    the container and copy it out with `$COMPOSE cp`.
- **Commits:** every commit message ends with the attribution trailer lines that the executing
  session's harness requires.

## Review Focus

1. **Compressed images.** A PACS that sends JPEG Lossless (the storage format of many PACS)
   must be accepted and stored as sent, not rejected during negotiation. Covered by Task 4,
   `test_compressed_images_are_accepted_as_sent`.
2. **Resent images.** A PACS that resends an image (after a timeout or a forward retry) must get
   success, and the spool must keep a single file. Covered by Task 3,
   `test_resending_an_image_replaces_it`.
3. **Disk full mid-write.** The router must answer `0xA700`, so the PACS retries later, and must
   leave no partial file in the spool. Covered by Task 3,
   `test_a_failed_write_leaves_no_partial_file`, and Task 4,
   `test_disk_full_while_writing_is_out_of_resources`.
4. **Database not migrated yet.** In development the router container starts before the web
   container has migrated the database. It must keep retrying instead of crashing. Covered by
   Task 5, `test_startup_waits_for_the_database`.
5. **Sender disabled while running.** A sender disabled in the Django admin must be refused
   within `ROUTER_SENDER_REFRESH_SECONDS`, without a restart. Images on its already open
   association get `0xA700`. Covered by Task 5,
   `test_disabling_a_sender_takes_effect_at_the_next_refresh`, and Task 4,
   `test_sender_disabled_during_an_open_association_is_refused`.

---

## File Structure

| File | Responsibility |
|---|---|
| `adit/core/utils/store_scp.py` (modify) | C-STORE SCP; gains an allow-list, a store handler, presentation contexts and a called-AE check |
| `adit/core/utils/presentation_contexts.py` (modify) | `storage_scp_contexts()` for an SCP that keeps data as received |
| `adit/router/apps.py` | app config; creates the `RouterSettings` row after migrate |
| `adit/router/models.py` | `RouterSettings`, `RouterSender` |
| `adit/router/admin.py` | Django admin for senders and settings |
| `adit/router/factories.py` | `RouterSenderFactory` for tests |
| `adit/router/migrations/0001_initial.py` | generated |
| `adit/router/utils/spool.py` | spool layout, UID check, durable store, tmp clean-up, free space |
| `adit/router/utils/intake.py` | `IntakeConfig`, `load_intake_config()`, `RouterStoreHandler`, `build_router_scp()` |
| `adit/router/management/commands/router.py` | the `router` command: start-up, refresh loop, shutdown |
| `adit/settings/base.py` (modify) | app registration and the `ROUTER_*` settings |
| `docker-compose.*.yml`, `orthanc/*.json`, `example.env` (modify) | the `router` service and its configuration |
| `adit/core/management/commands/populate_example_data.py` (modify) | registers Orthanc 1 as a sender |
| `CLAUDE.md`, `docs/user-docs/admin-guide.md` (modify) | docs |

Tests: `adit/core/tests/utils/test_store_scp.py` (extend),
`adit/core/tests/utils/test_presentation_contexts.py`, and `adit/router/tests/` with
`test_models.py`, `test_spool.py`, `test_intake.py`, `test_router_scp.py` and
`test_router_command.py`.

---

### Task 1: StoreScp options and storage contexts for the router

**Files:**
- Modify: `adit/core/utils/store_scp.py` (whole file shown below)
- Modify: `adit/core/utils/presentation_contexts.py:1-3` (imports) and the end of the file
- Test: `adit/core/tests/utils/test_store_scp.py` (append)
- Test: `adit/core/tests/utils/test_presentation_contexts.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces, in `adit/core/utils/store_scp.py`:
  - `StoreHandler = Callable[[Event], int]`
  - `StoreScp(folder, ae_title, host, port, debug=False, supported_contexts: list[PresentationContext] | None = None, require_called_aet: bool = False)`
  - `StoreScp.set_allowed_calling_aets(ae_titles: Iterable[str] | None) -> None`:
    - `None` accepts any AE title (the default);
    - an empty collection refuses every association;
    - entries are stripped.
  - `StoreScp.set_store_handler(handler: StoreHandler | None) -> None`
  - `StoreScp._allowed_calling_aets: frozenset[str] | None`, read by tests.
- Produces, in `adit/core/utils/presentation_contexts.py`:
  - `storage_scp_contexts() -> list[PresentationContext]`

- [ ] **Step 1: Write the failing StoreScp tests**

Add `from pynetdicom.ae import ApplicationEntity as AE` to the imports of
`adit/core/tests/utils/test_store_scp.py` and append:

```python
# ---------------------------------------------------------------------------
# Options used by the DICOM router
# ---------------------------------------------------------------------------


def test_custom_store_handler_decides_the_status(store_scp, monkeypatch):
    """With a store handler set, the handler stores the dataset and its return
    value is the C-STORE status; the default temp-file path is not used."""
    written: list[str] = []
    monkeypatch.setattr(store_scp_module, "write_dataset", lambda ds, fn: written.append(fn))

    seen: list[object] = []

    def handler(event):
        seen.append(event)
        return 0xA700

    store_scp.set_store_handler(handler)
    event = _make_event()

    assert store_scp._handle_store(event) == 0xA700
    assert seen == [event]
    assert written == []


def test_no_allow_list_accepts_every_calling_ae(store_scp):
    event = _make_event(calling_ae="ANYONE")

    store_scp._on_established(event)

    event.assoc.abort.assert_not_called()


def test_allow_list_aborts_associations_from_other_calling_aes(store_scp):
    store_scp.set_allowed_calling_aets(["PACS1"])
    allowed = _make_event(calling_ae="PACS1")
    other = _make_event(calling_ae="STRANGER")

    store_scp._on_established(allowed)
    store_scp._on_established(other)

    allowed.assoc.abort.assert_not_called()
    other.assoc.abort.assert_called_once()


def test_empty_allow_list_aborts_every_association(store_scp):
    store_scp.set_allowed_calling_aets([])
    event = _make_event(calling_ae="PACS1")

    store_scp._on_established(event)

    event.assoc.abort.assert_called_once()


def test_allow_list_is_handed_to_pynetdicom(store_scp):
    """A non-empty allow-list becomes pynetdicom's require_calling_aet, so unknown
    AEs are rejected during negotiation. pynetdicom reads [] as "anyone", so an
    empty allow-list maps to [] and _on_established aborts instead."""
    store_scp._ae = AE(ae_title="ADIT_RECEIVER")

    store_scp.set_allowed_calling_aets(["PACS2 ", "PACS1"])
    assert store_scp._ae.require_calling_aet == ["PACS1", "PACS2"]

    store_scp.set_allowed_calling_aets([])
    assert store_scp._ae.require_calling_aet == []

    store_scp.set_allowed_calling_aets(None)
    assert store_scp._ae.require_calling_aet == []
```

- [ ] **Step 2: Write the failing presentation context tests**

Create `adit/core/tests/utils/test_presentation_contexts.py`:

```python
from pydicom.uid import (
    BasicTextSRStorage,
    CTImageStorage,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEGLosslessSV1,
)
from pynetdicom.presentation import AllStoragePresentationContexts

from adit.core.utils.presentation_contexts import storage_scp_contexts


def _syntaxes_by_class() -> dict[str, list[str]]:
    return {
        str(cx.abstract_syntax): [str(ts) for ts in cx.transfer_syntax]
        for cx in storage_scp_contexts()
    }


def test_scp_contexts_cover_every_pynetdicom_storage_class():
    syntaxes = _syntaxes_by_class()

    for cx in AllStoragePresentationContexts:
        assert str(cx.abstract_syntax) in syntaxes


def test_scp_contexts_include_retired_classes_adit_knows():
    # Ultrasound Image Storage (Retired) is in ADIT's list but not in pynetdicom's.
    assert "1.2.840.10008.5.1.4.1.1.6" in _syntaxes_by_class()


def test_image_classes_accept_compressed_and_uncompressed_syntaxes():
    syntaxes = _syntaxes_by_class()[CTImageStorage]

    assert JPEGLosslessSV1 in syntaxes
    assert ImplicitVRLittleEndian in syntaxes
    assert ExplicitVRLittleEndian in syntaxes


def test_non_image_classes_accept_only_uncompressed_syntaxes():
    syntaxes = _syntaxes_by_class()[BasicTextSRStorage]

    assert ImplicitVRLittleEndian in syntaxes
    assert JPEGLosslessSV1 not in syntaxes
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_store_scp.py adit/core/tests/utils/test_presentation_contexts.py -v`

Expected: FAIL. The new StoreScp tests fail with
`AttributeError: 'StoreScp' object has no attribute 'set_store_handler'` (or
`set_allowed_calling_aets`), and the context tests fail with
`ImportError: cannot import name 'storage_scp_contexts'`. The existing receiver tests pass.

- [ ] **Step 4: Implement the StoreScp options**

Replace `adit/core/utils/store_scp.py` with:

```python
import argparse
import errno
import logging
import os
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile

from pynetdicom import debug_logger, evt
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.events import Event
from pynetdicom.presentation import AllStoragePresentationContexts, PresentationContext

from .dicom_utils import write_dataset

logger = logging.getLogger(__name__)

FileReceivedHandler = Callable[[str], None]
StoreHandler = Callable[[Event], int]


class StoreScp:
    _ae: AE | None = None
    _file_received_handler: FileReceivedHandler | None = None
    _store_handler: StoreHandler | None = None

    def __init__(
        self,
        folder: os.PathLike,
        ae_title: str,
        host: str,
        port: int,
        debug=False,
        supported_contexts: list[PresentationContext] | None = None,
        require_called_aet: bool = False,
    ):
        self._folder = folder
        self._ae_title = ae_title
        self._host = host
        self._port = port
        self._debug = debug
        self._supported_contexts = supported_contexts or AllStoragePresentationContexts
        self._require_called_aet = require_called_aet
        self._allowed_calling_aets: frozenset[str] | None = None
        self._stopped = threading.Event()

    def start(self):
        if self._debug:
            debug_logger()

        exists = os.path.exists(self._folder)
        is_dir = os.path.isdir(self._folder)
        if not exists or not is_dir:
            raise OSError(f"Invalid folder to store DICOM files: {self._folder}")

        self._ae = AE(ae_title=self._ae_title)

        # Speed up by reducing the number of required DIMSE messages
        # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
        self._ae.maximum_pdu_size = 0

        self._ae.supported_contexts = self._supported_contexts
        self._ae.require_called_aet = self._require_called_aet
        self._apply_allowed_calling_aets()

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

    def set_store_handler(self, handler: StoreHandler | None) -> None:
        """Let *handler* store each received dataset and return the C-STORE status."""
        self._store_handler = handler

    def set_allowed_calling_aets(self, ae_titles: Iterable[str] | None) -> None:
        """Only accept associations from these calling AE titles; None accepts any.

        An empty collection refuses every association.
        """
        self._allowed_calling_aets = (
            None if ae_titles is None else frozenset(title.strip() for title in ae_titles)
        )
        self._apply_allowed_calling_aets()

    def _apply_allowed_calling_aets(self) -> None:
        if self._ae is None:
            return
        # pynetdicom reads an empty list as "accept any AE title", so an empty
        # allow-list is enforced by _on_established instead.
        self._ae.require_calling_aet = sorted(self._allowed_calling_aets or [])

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

        allowed = self._allowed_calling_aets
        if allowed is not None and calling_ae.strip() not in allowed:
            logger.warning(
                "Association from %s [%s:%d] refused: calling AE title not allowed.",
                calling_ae,
                address,
                port,
            )
            event.assoc.abort()
            return

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

        Without a store handler the request is a sub-operation of a C-MOVE that ADIT
        itself started, to fetch images from a DICOM server that doesn't support C-GET.
        """
        if self._store_handler:
            return self._store_handler(event)

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
```

- [ ] **Step 5: Implement `storage_scp_contexts()`**

In `adit/core/utils/presentation_contexts.py`, replace the import block at the top:

```python
from pynetdicom.presentation import (
    build_context,
)
```

with:

```python
from pynetdicom._globals import DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.presentation import (
    AllStoragePresentationContexts,
    PresentationContext,
    build_context,
)
```

and append at the end of the file:

```python


def storage_scp_contexts() -> list[PresentationContext]:
    """Presentation contexts for a Storage SCP that keeps datasets as received.

    Covers every storage SOP class pynetdicom knows plus the ones listed above, with
    pynetdicom's default transfer syntaxes. Image SOP classes are also accepted in the
    compressed transfer syntaxes, as the SCP stores pixel data without decoding it.
    """
    default_syntaxes = [str(ts) for ts in DEFAULT_TRANSFER_SYNTAXES]
    image_storage = set(_image_storage)
    uids = {str(cx.abstract_syntax) for cx in AllStoragePresentationContexts}
    uids |= image_storage | set(_non_image_storage)
    return [
        build_context(
            uid,
            default_syntaxes + _compressed_transfer_syntaxes
            if uid in image_storage
            else default_syntaxes,
        )
        for uid in sorted(uids)
    ]
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `uv run cli test -- adit/core/tests/utils/test_store_scp.py adit/core/tests/utils/test_presentation_contexts.py -v`

Expected: PASS, including every existing receiver test.

- [ ] **Step 7: Commit**

```bash
git add adit/core/utils/store_scp.py adit/core/utils/presentation_contexts.py \
  adit/core/tests/utils/test_store_scp.py adit/core/tests/utils/test_presentation_contexts.py
git commit -m "Let StoreScp restrict calling AE titles and delegate storing"
```

---

### Task 2: Router app with senders and settings

**Files:**
- Create: `adit/router/__init__.py` (empty)
- Create: `adit/router/apps.py`
- Create: `adit/router/models.py`
- Create: `adit/router/admin.py`
- Create: `adit/router/factories.py`
- Create: `adit/router/migrations/__init__.py` (empty)
- Create: `adit/router/migrations/0001_initial.py` (generated in Step 5)
- Create: `adit/router/tests/__init__.py` (empty)
- Modify: `adit/settings/base.py:93`, in `INSTALLED_APPS`
- Test: `adit/router/tests/test_models.py`

**Interfaces:**
- Consumes: `adit.core.models.DicomAppSettings`, `adit.core.models.DicomServer`,
  `adit.core.factories.DicomServerFactory`.
- Produces:
  - `RouterSettings(DicomAppSettings)`, with fields `locked` and `suspended`;
    `RouterSettings.get()` returns the single row.
  - `RouterSender`, with fields:
    - `server` (`OneToOneField(DicomServer)`, `related_name="router_sender"`);
    - `calling_ae_title: str` (unique, at most 16 characters, stripped; filled from
      `server.ae_title` when empty);
    - `enabled: bool`.
  - `RouterSenderFactory`, whose `server` is a `SubFactory(DicomServerFactory)` and whose
    `calling_ae_title` follows the sequence `SENDER<n>`.

- [ ] **Step 1: Write the failing model tests**

Create `adit/router/tests/__init__.py` (empty) and `adit/router/tests/test_models.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from adit.core.factories import DicomServerFactory
from adit.router.factories import RouterSenderFactory
from adit.router.models import RouterSender, RouterSettings


@pytest.mark.django_db
def test_router_settings_row_exists_after_migrate():
    router_settings = RouterSettings.get()

    assert isinstance(router_settings, RouterSettings)
    assert router_settings.suspended is False


@pytest.mark.django_db
def test_sender_defaults_calling_ae_title_to_the_server_ae_title():
    server = DicomServerFactory.create(ae_title="PACS1")

    sender = RouterSender.objects.create(server=server)

    assert sender.calling_ae_title == "PACS1"


@pytest.mark.django_db
def test_sender_keeps_a_different_sending_ae_title_stripped():
    server = DicomServerFactory.create(ae_title="PACS_QR")

    sender = RouterSender.objects.create(server=server, calling_ae_title=" PACS_SEND ")

    assert sender.calling_ae_title == "PACS_SEND"


@pytest.mark.django_db
def test_full_clean_fills_the_calling_ae_title_for_the_admin_form():
    server = DicomServerFactory.create(ae_title="PACS1")
    sender = RouterSender(server=server)

    sender.full_clean()

    assert sender.calling_ae_title == "PACS1"


@pytest.mark.django_db
def test_calling_ae_titles_are_unique():
    RouterSenderFactory.create(calling_ae_title="PACS1")

    with pytest.raises(IntegrityError):
        RouterSenderFactory.create(calling_ae_title="PACS1")


@pytest.mark.django_db
def test_calling_ae_title_rejects_a_backslash():
    sender = RouterSender(server=DicomServerFactory.create(), calling_ae_title="PA\\CS")

    with pytest.raises(ValidationError) as exc_info:
        sender.full_clean()

    assert "calling_ae_title" in exc_info.value.message_dict
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run cli test -- adit/router/tests/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'adit.router.factories'` (or
`adit.router.models`).

- [ ] **Step 3: Create the app, models, admin and factory**

`adit/router/__init__.py` and `adit/router/migrations/__init__.py`: empty files.

`adit/router/models.py`:

```python
from django.db import models

from adit.core.models import DicomAppSettings, DicomServer
from adit.core.validators import no_backslash_char_validator, no_control_chars_validator


class RouterSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Router settings"


class RouterSender(models.Model):
    server_id: int
    server = models.OneToOneField(
        DicomServer, on_delete=models.PROTECT, related_name="router_sender"
    )
    calling_ae_title = models.CharField(
        unique=True,
        max_length=16,
        blank=True,
        default="",
        validators=[no_backslash_char_validator, no_control_chars_validator],
        help_text="The AE title the server sends from. Leave empty to use its AE title.",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("calling_ae_title",)

    def __str__(self) -> str:
        return f"Router sender {self.calling_ae_title}"

    def save(self, *args, **kwargs) -> None:
        self.calling_ae_title = self.calling_ae_title.strip() or self.server.ae_title
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.server_id:
            self.calling_ae_title = self.calling_ae_title.strip() or self.server.ae_title
```

`adit/router/apps.py`:

```python
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RouterConfig(AppConfig):
    name = "adit.router"

    def ready(self):
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)


def init_db(**kwargs):
    from .models import RouterSettings

    if not RouterSettings.objects.exists():
        RouterSettings.objects.create()
```

`adit/router/admin.py`:

```python
from django.contrib import admin

from .models import RouterSender, RouterSettings


class RouterSenderAdmin(admin.ModelAdmin):
    list_display = ("calling_ae_title", "server", "enabled")
    list_filter = ("enabled",)


admin.site.register(RouterSender, RouterSenderAdmin)
admin.site.register(RouterSettings, admin.ModelAdmin)
```

`adit/router/factories.py`:

```python
import factory
from adit_radis_shared.common.factories import BaseDjangoModelFactory

from adit.core.factories import DicomServerFactory

from .models import RouterSender


class RouterSenderFactory(BaseDjangoModelFactory[RouterSender]):
    class Meta:
        model = RouterSender

    server = factory.SubFactory(DicomServerFactory)
    calling_ae_title = factory.Sequence(lambda n: f"SENDER{n}")
    enabled = True
```

- [ ] **Step 4: Register the app**

In `adit/settings/base.py`, in `INSTALLED_APPS`, add the router after the DICOMweb app:

```python
    "adit.dicom_web.apps.DicomWebConfig",
    "adit.router.apps.RouterConfig",
    "channels",
```

- [ ] **Step 5: Generate the migration and copy it to the host**

The dev containers receive host edits through `compose watch`, but files created inside a
container don't come back by themselves.

Run:

```bash
$COMPOSE exec web ./manage.py makemigrations router
$COMPOSE cp web:/app/adit/router/migrations/0001_initial.py adit/router/migrations/0001_initial.py
$COMPOSE exec web ./manage.py makemigrations --check --dry-run
```

Expected:
- The first command prints `Migrations for 'router':`, followed by
  `adit/router/migrations/0001_initial.py`, `+ Create model RouterSettings` and
  `+ Create model RouterSender`.
- The last command prints `No changes detected`.

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `uv run cli test -- adit/router/tests/test_models.py -v`

Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add adit/router adit/settings/base.py
git commit -m "Add the router app with senders and settings"
```

---

### Task 3: Durable spool writes

**Files:**
- Create: `adit/router/utils/__init__.py` (empty)
- Create: `adit/router/utils/spool.py`
- Test: `adit/router/tests/test_spool.py`

**Interfaces:**
- Consumes: `adit.core.utils.dicom_utils.write_dataset(ds, fn)`.
- Produces, in `adit/router/utils/spool.py`:
  - Folder names: `TMP = "tmp"`, `INCOMING = "incoming"`, `BATCHES = "batches"`,
    `QUARANTINE = "quarantine"`.
  - Errors: `InvalidUidError(ValueError)` and `SpoolError(OSError)`.
  - `is_valid_uid(value: object) -> bool`
  - `ensure_spool_dirs(spool_root: Path) -> None`
  - `incoming_study_dir(spool_root: Path, sender_id: int, study_uid: str) -> Path`
  - `store_dataset(spool_root: Path, sender_id: int, ds: Dataset) -> Path`. It raises
    `InvalidUidError` for bad UIDs and `OSError` (including `SpoolError`) when writing fails.
    It never leaves a file in `tmp/`.
  - `clean_tmp(spool_root: Path) -> int`
  - `free_bytes(spool_root: Path) -> int`

- [ ] **Step 1: Write the failing spool tests**

Create `adit/router/tests/test_spool.py`:

```python
import errno
import os
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from adit.core.utils.dicom_utils import read_dataset
from adit.router.utils import spool


def _dataset(study_uid: str | None = None, instance_uid: str | None = None) -> Dataset:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = instance_uid or generate_uid()
    ds.StudyInstanceUID = study_uid or generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientID = "1001"
    ds.Modality = "CT"
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    return ds


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def test_ensure_spool_dirs_creates_the_layout(tmp_path):
    spool.ensure_spool_dirs(tmp_path)

    for name in (spool.TMP, spool.INCOMING, spool.BATCHES, spool.QUARANTINE):
        assert (tmp_path / name).is_dir()


def test_store_dataset_writes_into_the_senders_study_folder(spool_root):
    ds = _dataset()

    path = spool.store_dataset(spool_root, 7, ds)

    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert read_dataset(path).SOPInstanceUID == ds.SOPInstanceUID


def test_store_dataset_leaves_nothing_in_tmp(spool_root):
    spool.store_dataset(spool_root, 7, _dataset())

    assert list((spool_root / spool.TMP).iterdir()) == []


def test_resending_an_image_replaces_it(spool_root):
    study_uid, instance_uid = generate_uid(), generate_uid()

    spool.store_dataset(spool_root, 7, _dataset(study_uid, instance_uid))
    spool.store_dataset(spool_root, 7, _dataset(study_uid, instance_uid))

    study_dir = spool_root / spool.INCOMING / "7" / study_uid
    assert [p.name for p in study_dir.iterdir()] == [f"{instance_uid}.dcm"]


@pytest.mark.parametrize("bad_uid", ["", "../../etc", "1.2.x", "1..2", "1" * 65, None])
def test_store_dataset_refuses_uids_that_are_not_path_safe(spool_root, bad_uid):
    ds = _dataset()
    if bad_uid is None:
        del ds.StudyInstanceUID
    else:
        with pydicom_config.disable_value_validation():
            ds.StudyInstanceUID = bad_uid

    with pytest.raises(spool.InvalidUidError):
        spool.store_dataset(spool_root, 7, ds)

    assert list((spool_root / spool.TMP).iterdir()) == []
    assert list((spool_root / spool.INCOMING).iterdir()) == []


def test_image_arriving_while_its_study_folder_closes_starts_a_new_folder(
    spool_root, monkeypatch
):
    """The closing task (stage 3) renames a quiet study folder to batches/. If that
    happens between the router creating the folder and moving the image in, the move
    fails and the image lands in a fresh study folder: the next batch."""
    ds = _dataset()
    study_dir = spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    closed_dir = spool_root / spool.BATCHES / "7" / "closed"
    closed_dir.parent.mkdir(parents=True)
    real_replace = os.replace
    targets: list[str] = []

    def replace_racing_with_close(src, dst):
        if not targets:
            os.rename(study_dir, closed_dir)
        targets.append(str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(spool.os, "replace", replace_racing_with_close)

    path = spool.store_dataset(spool_root, 7, ds)

    assert len(targets) == 2
    assert path == study_dir / f"{ds.SOPInstanceUID}.dcm"
    assert path.is_file()
    assert list(closed_dir.iterdir()) == []


def test_a_failed_write_leaves_no_partial_file(spool_root, monkeypatch):
    def write_then_fail(ds, f):
        f.write(b"partial")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(spool, "write_dataset", write_then_fail)

    with pytest.raises(OSError):
        spool.store_dataset(spool_root, 7, _dataset())

    assert list((spool_root / spool.TMP).iterdir()) == []
    assert list((spool_root / spool.INCOMING).rglob("*.dcm")) == []


def test_clean_tmp_removes_leftovers_of_a_crash(spool_root):
    (spool_root / spool.TMP / "abc.dcm").write_bytes(b"partial")

    assert spool.clean_tmp(spool_root) == 1
    assert list((spool_root / spool.TMP).iterdir()) == []


def test_free_bytes_reports_the_spool_filesystem(spool_root):
    assert spool.free_bytes(spool_root) > 0
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run cli test -- adit/router/tests/test_spool.py -v`

Expected: FAIL with `ImportError: cannot import name 'spool' from 'adit.router.utils'` (or
`ModuleNotFoundError`).

- [ ] **Step 3: Implement the spool module**

Create `adit/router/utils/__init__.py` (empty) and `adit/router/utils/spool.py`:

```python
"""The router's spool: images on disk between receiving and routing.

All folders live on one filesystem, so moving a file or folder inside the spool is a
single atomic rename.
"""

import os
import re
import shutil
import uuid
from pathlib import Path

from pydicom import Dataset

from adit.core.utils.dicom_utils import write_dataset

TMP = "tmp"
INCOMING = "incoming"
BATCHES = "batches"
QUARANTINE = "quarantine"

# UIDs become path components, so only the UID character set is accepted.
_UID_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_MAX_UID_LENGTH = 64

# A move into a study folder only fails when that folder is closed at the same
# moment, so a retry nearly always succeeds.
_MAX_MOVE_ATTEMPTS = 5


class InvalidUidError(ValueError):
    pass


class SpoolError(OSError):
    pass


def is_valid_uid(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= _MAX_UID_LENGTH
        and _UID_PATTERN.match(value) is not None
    )


def ensure_spool_dirs(spool_root: Path) -> None:
    for name in (TMP, INCOMING, BATCHES, QUARANTINE):
        (spool_root / name).mkdir(parents=True, exist_ok=True)


def incoming_study_dir(spool_root: Path, sender_id: int, study_uid: str) -> Path:
    return spool_root / INCOMING / str(sender_id) / study_uid


def store_dataset(spool_root: Path, sender_id: int, ds: Dataset) -> Path:
    """Write *ds* durably into its open study folder and return the file path.

    The file is written to tmp/ and flushed to disk first, then moved into the study
    folder, so a study folder never holds a partial file. When the study folder is
    closed between creating it and moving the file in, the move fails and the image
    starts a new study folder.
    """
    study_uid = ds.get("StudyInstanceUID")
    instance_uid = ds.get("SOPInstanceUID")
    if not is_valid_uid(study_uid) or not is_valid_uid(instance_uid):
        raise InvalidUidError(
            f"Invalid Study or SOP Instance UID: {study_uid!r}, {instance_uid!r}"
        )

    tmp_path = spool_root / TMP / f"{uuid.uuid4().hex}.dcm"
    try:
        with open(tmp_path, "wb") as f:
            write_dataset(ds, f)
            f.flush()
            os.fsync(f.fileno())
        study_dir = incoming_study_dir(spool_root, sender_id, study_uid)
        return _move_into_study_dir(tmp_path, study_dir, f"{instance_uid}.dcm")
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def clean_tmp(spool_root: Path) -> int:
    """Delete files left in tmp/ by a crash while writing; returns how many."""
    removed = 0
    for path in (spool_root / TMP).iterdir():
        path.unlink()
        removed += 1
    return removed


def free_bytes(spool_root: Path) -> int:
    return shutil.disk_usage(spool_root).free


def _move_into_study_dir(tmp_path: Path, study_dir: Path, filename: str) -> Path:
    for _ in range(_MAX_MOVE_ATTEMPTS):
        _ensure_dir(study_dir)
        try:
            # Opened before the move so the fsync reaches the folder even if it is
            # renamed to batches/ right after the move.
            dir_fd = os.open(study_dir, os.O_RDONLY)
        except FileNotFoundError:
            continue
        try:
            os.replace(tmp_path, study_dir / filename)
            os.fsync(dir_fd)
            return study_dir / filename
        except FileNotFoundError:
            continue
        finally:
            os.close(dir_fd)
    raise SpoolError(f"Could not move {filename} into {study_dir}.")


def _ensure_dir(path: Path) -> None:
    """Create *path* and its parents, flushing each new folder entry to disk."""
    if path.is_dir():
        return
    _ensure_dir(path.parent)
    try:
        path.mkdir()
    except FileExistsError:
        return
    _fsync_dir(path.parent)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run cli test -- adit/router/tests/test_spool.py -v`

Expected: PASS (14 tests, counting each parametrized case).

- [ ] **Step 5: Commit**

```bash
git add adit/router/utils/__init__.py adit/router/utils/spool.py adit/router/tests/test_spool.py
git commit -m "Write router images durably into a study spool"
```

---

### Task 4: Router intake: senders, C-STORE handler and SCP

**Files:**
- Create: `adit/router/utils/intake.py`
- Test: `adit/router/tests/test_intake.py`
- Test: `adit/router/tests/test_router_scp.py`

**Interfaces:**
- Consumes:
  - `StoreScp`, `set_store_handler` and `set_allowed_calling_aets` (Task 1);
  - `storage_scp_contexts()` (Task 1);
  - `RouterSender`, `RouterSettings` and `RouterSenderFactory` (Task 2);
  - the `spool` module (Task 3).
- Produces, in `adit/router/utils/intake.py`:
  - Status constants: `STATUS_SUCCESS = 0x0000`, `STATUS_OUT_OF_RESOURCES = 0xA700`,
    `STATUS_CANNOT_UNDERSTAND = 0xC000`.
  - `IntakeConfig`, a frozen dataclass with `sender_ids: dict[str, int]` (calling AE title →
    `RouterSender.pk`) and `suspended: bool`. `REFUSE_ALL = IntakeConfig(sender_ids={}, suspended=True)`.
  - `load_intake_config() -> IntakeConfig`
  - `RouterStoreHandler(spool_root: Path, min_free_bytes: int)`, with
    `.config -> IntakeConfig`, `.update_config(config: IntakeConfig) -> None` and
    `__call__(event: Event) -> int`. It starts as `REFUSE_ALL`.
  - `build_router_scp(spool_root: Path, handler: RouterStoreHandler, ae_title: str, host: str, port: int, debug: bool = False) -> StoreScp`

- [ ] **Step 1: Write the failing handler and config tests**

Create `adit/router/tests/test_intake.py`:

```python
import errno
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from adit.router.factories import RouterSenderFactory
from adit.router.models import RouterSettings
from adit.router.utils import spool
from adit.router.utils.intake import IntakeConfig, RouterStoreHandler, load_intake_config


def _event(calling_ae: str = "PACS1") -> MagicMock:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    event = MagicMock()
    event.assoc.remote = {"ae_title": calling_ae, "address": "10.0.0.1", "port": 104}
    event.dataset = ds
    event.file_meta = file_meta
    return event


def _spooled(spool_root: Path) -> list[Path]:
    return list((spool_root / spool.INCOMING).rglob("*.dcm"))


def _handler(spool_root: Path, min_free_bytes: int = 0) -> RouterStoreHandler:
    spool.ensure_spool_dirs(spool_root)
    handler = RouterStoreHandler(spool_root, min_free_bytes=min_free_bytes)
    handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=False))
    return handler


def test_image_from_an_enabled_sender_is_spooled(tmp_path):
    event = _event()

    assert _handler(tmp_path)(event) == 0x0000

    [path] = _spooled(tmp_path)
    assert path.parent == tmp_path / spool.INCOMING / "7" / event.dataset.StudyInstanceUID


def test_new_handler_refuses_everything_until_configured(tmp_path):
    spool.ensure_spool_dirs(tmp_path)
    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_sender_disabled_during_an_open_association_is_refused(tmp_path):
    handler = _handler(tmp_path)
    handler.update_config(IntakeConfig(sender_ids={}, suspended=False))

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_suspended_router_refuses_images(tmp_path):
    handler = _handler(tmp_path)
    handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=True))

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_low_spool_space_refuses_images(tmp_path):
    handler = _handler(tmp_path, min_free_bytes=10**18)

    assert handler(_event()) == 0xA700
    assert _spooled(tmp_path) == []


def test_image_with_an_unsafe_uid_is_not_understood(tmp_path):
    event = _event()
    with pydicom_config.disable_value_validation():
        event.dataset.StudyInstanceUID = "../../etc"

    assert _handler(tmp_path)(event) == 0xC000
    assert _spooled(tmp_path) == []


def test_disk_full_while_writing_is_out_of_resources(tmp_path, monkeypatch):
    def disk_full(ds, f):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(spool, "write_dataset", disk_full)

    assert _handler(tmp_path)(_event()) == 0xA700
    assert list((tmp_path / spool.TMP).iterdir()) == []
    assert _spooled(tmp_path) == []


@pytest.mark.django_db
def test_load_intake_config_lists_enabled_senders_and_the_suspended_flag():
    enabled = RouterSenderFactory.create(calling_ae_title="PACS1")
    RouterSenderFactory.create(calling_ae_title="OLDPACS", enabled=False)
    RouterSettings.objects.update(suspended=True)

    config = load_intake_config()

    assert config == IntakeConfig(sender_ids={"PACS1": enabled.pk}, suspended=True)
```

- [ ] **Step 2: Write the failing network tests**

Create `adit/router/tests/test_router_scp.py`. These start a real listener on 127.0.0.1 and
talk to it with a pynetdicom SCU. They are wired exactly as the `router` command wires the
listener.

```python
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, JPEGLosslessSV1, generate_uid
from pynetdicom import AE
from pynetdicom.association import Association

from adit.core.utils.store_scp import StoreScp
from adit.router.utils import spool
from adit.router.utils.intake import IntakeConfig, RouterStoreHandler, build_router_scp

ROUTER_AE = "ROUTERTEST"


@dataclass
class Router:
    scp: StoreScp
    handler: RouterStoreHandler
    port: int
    spool_root: Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_listening(port: int) -> None:
    deadline = time.monotonic() + 5
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


@pytest.fixture
def router(tmp_path: Path) -> Iterator[Router]:
    spool.ensure_spool_dirs(tmp_path)
    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)
    handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=False))
    port = _free_port()
    scp = build_router_scp(tmp_path, handler, ae_title=ROUTER_AE, host="127.0.0.1", port=port)
    thread = threading.Thread(target=scp.start, daemon=True)
    thread.start()
    _wait_until_listening(port)
    yield Router(scp, handler, port, tmp_path)
    scp.stop()
    thread.join(timeout=5)


def _associate(
    port: int,
    calling_ae: str,
    called_ae: str = ROUTER_AE,
    transfer_syntax: str = ExplicitVRLittleEndian,
) -> Association:
    ae = AE(ae_title=calling_ae)
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.add_requested_context(CTImageStorage, transfer_syntax)
    return ae.associate("127.0.0.1", port, ae_title=called_ae)


def _ct_image() -> Dataset:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientID = "1001"
    ds.Modality = "CT"
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    return ds


def test_known_sender_stores_an_image_in_its_study_folder(router):
    ds = _ct_image()
    assoc = _associate(router.port, "PACS1")
    assert assoc.is_established

    status = assoc.send_c_store(ds)
    assoc.release()

    assert status.Status == 0x0000
    study_dir = router.spool_root / spool.INCOMING / "7" / ds.StudyInstanceUID
    assert (study_dir / f"{ds.SOPInstanceUID}.dcm").is_file()


def test_unknown_sender_is_rejected(router):
    assoc = _associate(router.port, "STRANGER")

    assert assoc.is_rejected


def test_wrong_called_ae_title_is_rejected(router):
    assoc = _associate(router.port, "PACS1", called_ae="SOMEONEELSE")

    assert assoc.is_rejected


def test_no_enabled_sender_refuses_every_association(router):
    router.scp.set_allowed_calling_aets([])

    assoc = _associate(router.port, "PACS1")

    assert assoc.is_aborted
    assert not assoc.is_established


def test_compressed_images_are_accepted_as_sent(router):
    """Many PACS store and forward JPEG Lossless; the router accepts it unchanged."""
    assoc = _associate(router.port, "PACS1", transfer_syntax=JPEGLosslessSV1)
    assert assoc.is_established

    accepted = [str(cx.transfer_syntax[0]) for cx in assoc.accepted_contexts]
    assoc.release()

    assert accepted == [JPEGLosslessSV1]


def test_suspended_router_answers_out_of_resources(router):
    router.handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=True))
    assoc = _associate(router.port, "PACS1")

    status = assoc.send_c_store(_ct_image())
    assoc.release()

    assert status.Status == 0xA700
    assert list((router.spool_root / spool.INCOMING).rglob("*.dcm")) == []
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `uv run cli test -- adit/router/tests/test_intake.py adit/router/tests/test_router_scp.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'adit.router.utils.intake'`.

- [ ] **Step 4: Implement the intake**

Create `adit/router/utils/intake.py`:

```python
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
    router_settings = RouterSettings.get()
    assert isinstance(router_settings, RouterSettings)
    senders = RouterSender.objects.filter(enabled=True).values_list("calling_ae_title", "pk")
    return IntakeConfig(
        sender_ids={ae_title.strip(): pk for ae_title, pk in senders},
        suspended=router_settings.suspended,
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
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `uv run cli test -- adit/router/tests/test_intake.py adit/router/tests/test_router_scp.py -v`

Expected: PASS (14 tests).

- [ ] **Step 6: Commit**

```bash
git add adit/router/utils/intake.py adit/router/tests/test_intake.py adit/router/tests/test_router_scp.py
git commit -m "Decide router C-STORE statuses and spool accepted images"
```

---

### Task 5: The `router` command and its settings

**Files:**
- Create: `adit/router/management/__init__.py` (empty)
- Create: `adit/router/management/commands/__init__.py` (empty)
- Create: `adit/router/management/commands/router.py`
- Modify: `adit/settings/base.py`, after line 405 (`FILE_TRANSMIT_PORT = ...`)
- Test: `adit/router/tests/test_router_command.py`

**Interfaces:**
- Consumes:
  - `build_router_scp`, `load_intake_config`, `RouterStoreHandler` and `IntakeConfig`
    (Task 4);
  - `spool.ensure_spool_dirs` and `spool.clean_tmp` (Task 3);
  - `StoreScp.set_allowed_calling_aets` and `StoreScp._allowed_calling_aets` (Task 1);
  - `RouterSenderFactory` (Task 2).
- Produces:
  - The settings `ROUTER_AE_TITLE` (str, default `""`), `ROUTER_SCP_PORT` (int, default
    11112), `ROUTER_SPOOL_PATH` (str, default `"/spool"`), `ROUTER_SENDER_REFRESH_SECONDS`
    (int, default 30) and `ROUTER_SPOOL_MIN_FREE_GB` (int, default 20).
  - `./manage.py router [--autoreload]`.
  - In the command module: `STARTUP_RETRY_SECONDS = 5`, `Command._stopped: threading.Event`,
    `Command._refresh(store_scp, handler) -> None`,
    `Command._load_config_until_ready(store_scp, handler) -> bool` and
    `Command._refresh_periodically(store_scp, handler) -> None`.

- [ ] **Step 1: Write the failing command tests**

Create `adit/router/tests/test_router_command.py`:

```python
import io

import pytest
from django.db import ProgrammingError

from adit.router.factories import RouterSenderFactory
from adit.router.management.commands import router as router_command
from adit.router.utils import spool
from adit.router.utils.intake import IntakeConfig, RouterStoreHandler, build_router_scp


@pytest.fixture
def command() -> router_command.Command:
    return router_command.Command(stdout=io.StringIO())


@pytest.fixture
def handler_and_scp(tmp_path):
    spool.ensure_spool_dirs(tmp_path)
    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)
    scp = build_router_scp(tmp_path, handler, ae_title="ROUTERTEST", host="127.0.0.1", port=11112)
    return handler, scp


def test_router_without_ae_title_is_disabled(command, settings):
    settings.ROUTER_AE_TITLE = ""
    command._stopped.set()

    command.run_server()

    assert "disabled" in command.stdout.getvalue()


@pytest.mark.django_db
def test_refresh_applies_senders_and_suspension_to_scp_and_handler(command, handler_and_scp):
    handler, scp = handler_and_scp
    sender = RouterSenderFactory.create(calling_ae_title="PACS1")

    command._refresh(scp, handler)

    assert handler.config == IntakeConfig(sender_ids={"PACS1": sender.pk}, suspended=False)
    assert scp._allowed_calling_aets == frozenset({"PACS1"})


@pytest.mark.django_db
def test_disabling_a_sender_takes_effect_at_the_next_refresh(command, handler_and_scp):
    handler, scp = handler_and_scp
    sender = RouterSenderFactory.create(calling_ae_title="PACS1")
    command._refresh(scp, handler)

    sender.enabled = False
    sender.save()
    command._refresh(scp, handler)

    assert handler.config.sender_ids == {}
    assert scp._allowed_calling_aets == frozenset()


def test_startup_waits_for_the_database(command, handler_and_scp, monkeypatch):
    handler, scp = handler_and_scp
    attempts: list[int] = []

    def flaky_load():
        attempts.append(1)
        if len(attempts) == 1:
            raise ProgrammingError('relation "router_routersettings" does not exist')
        return IntakeConfig(sender_ids={"PACS1": 1}, suspended=False)

    monkeypatch.setattr(router_command, "load_intake_config", flaky_load)
    monkeypatch.setattr(router_command, "STARTUP_RETRY_SECONDS", 0)

    assert command._load_config_until_ready(scp, handler) is True
    assert len(attempts) == 2
    assert handler.config.sender_ids == {"PACS1": 1}


def test_startup_gives_up_when_the_command_stops(command, handler_and_scp, monkeypatch):
    handler, scp = handler_and_scp

    def broken_load():
        command._stopped.set()
        raise ProgrammingError('relation "router_routersettings" does not exist')

    monkeypatch.setattr(router_command, "load_intake_config", broken_load)
    monkeypatch.setattr(router_command, "STARTUP_RETRY_SECONDS", 0)

    assert command._load_config_until_ready(scp, handler) is False
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run cli test -- adit/router/tests/test_router_command.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'adit.router.management'`.

- [ ] **Step 3: Add the settings**

In `adit/settings/base.py`, directly after
`FILE_TRANSMIT_PORT = env.int("FILE_TRANSMIT_PORT", 14638)`, add:

```python

# The AE title of the DICOM router. Senders forward studies to it. Empty disables the router.
ROUTER_AE_TITLE = env.str("ROUTER_AE_TITLE", default="")

# The port the DICOM router listens on inside its container.
ROUTER_SCP_PORT = env.int("ROUTER_SCP_PORT", default=11112)

# The folder of the router spool inside the containers.
ROUTER_SPOOL_PATH = env.str("ROUTER_SPOOL_PATH", default="/spool")

# How often the router reloads its senders and the suspended flag from the database.
ROUTER_SENDER_REFRESH_SECONDS = env.int("ROUTER_SENDER_REFRESH_SECONDS", default=30)

# The router refuses new images while the spool has less free space than this.
ROUTER_SPOOL_MIN_FREE_GB = env.int("ROUTER_SPOOL_MIN_FREE_GB", default=20)
```

- [ ] **Step 4: Implement the command**

Create the empty `adit/router/management/__init__.py` and
`adit/router/management/commands/__init__.py`, then
`adit/router/management/commands/router.py`:

```python
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
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `uv run cli test -- adit/router/tests/test_router_command.py -v`

Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add adit/router/management adit/router/tests/test_router_command.py adit/settings/base.py
git commit -m "Add the router command that runs the router SCP"
```

---

### Task 6: Router container, example data and docs

**Files:**
- Modify: `docker-compose.base.yml` (a new `router` service, and `router_spool` under `volumes:`)
- Modify: `docker-compose.dev.yml` (a new `router` service after `receiver`)
- Modify: `docker-compose.prod.yml` (a new `router` service after `receiver`)
- Modify: `orthanc/orthanc1.json:8-11` and `orthanc/orthanc2.json:8-11` (`DicomModalities`)
- Modify: `example.env` (the production ports block, plus the AE title block after `RECEIVER_AE_TITLE`)
- Modify: `adit/core/management/commands/populate_example_data.py` (`create_server_nodes`)
- Modify: `CLAUDE.md` (lines 46, 77, 148, 160 and 185)
- Modify: `docs/user-docs/admin-guide.md:31` (the "Optional tuning" paragraph)

**Interfaces:**
- Consumes: the `router` command and the `ROUTER_*` settings (Task 5); `RouterSender` (Task 2).
- Produces:
  - The `router` service, with hostname `router.local` and the spool at `/spool`. The spool is
    the named volume `router_spool`, or `ROUTER_SPOOL_DIR` if that is set.
  - The Orthanc test servers know the modality `ROUTER` = `ADIT1DEVROUTER@router:11112`.

- [ ] **Step 1: Add the router service to the compose files**

Only the router mounts the spool in this stage. The spec's mounts on `default_worker` and
`dicom_worker` come with stage 3, when the workers start reading the spool. The router's
`volumes:` replaces the anchor's list, so it doesn't get `/backups` or `/mnt`, which it doesn't
need.

In `docker-compose.base.yml`, after the `receiver` service, add:

```yaml
  router:
    <<: *default-app
    hostname: router.local
    volumes:
      - ${ROUTER_SPOOL_DIR:-router_spool}:/spool
```

and add `router_spool:` to the top-level `volumes:` block:

```yaml
volumes:
  postgres_data:
  orthanc1_data:
  orthanc2_data:
  router_spool:
```

In `docker-compose.dev.yml`, after the `receiver` service, add:

```yaml
  router:
    <<: *default-app
    image: adit_dev-router:latest
    ports:
      - 11123:11112
    command: >
      bash -c "
        wait-for-it -s postgres.local:5432 -t ${WAIT_POSTGRES_TIMEOUT:-180} &&
        ./manage.py router --autoreload
      "
```

In `docker-compose.prod.yml`, after the `receiver` service, add:

```yaml
  router:
    <<: *default-app
    ports:
      - ${ROUTER_PORT:-11113}:11112
    command: >
      bash -c "
        wait-for-it -s init.local:8000 -t 300 &&
        ./manage.py router
      "
    deploy:
      <<: *deploy
```

- [ ] **Step 2: Validate the compose files**

Run:

```bash
PROJECT_VERSION=0.0.0 docker compose -f docker-compose.base.yml -f docker-compose.dev.yml -p adit_dev config --quiet && echo dev-ok
PROJECT_VERSION=0.0.0 docker compose -f docker-compose.base.yml -f docker-compose.prod.yml -p adit_prod config --quiet && echo prod-ok
```

Expected: `dev-ok` and `prod-ok`, with no errors. `PROJECT_VERSION` is normally set by the CLI;
the base file requires it.

- [ ] **Step 3: Let the Orthanc test servers send to the router**

In `orthanc/orthanc1.json`, change `DicomModalities` to:

```json
  "DicomModalities": {
    "ORTHANC2": ["ORTHANC2", "orthanc2", 7502],
    "ADIT": ["ADIT1DEV", "receiver", 11112],
    "ROUTER": ["ADIT1DEVROUTER", "router", 11112]
  },
```

In `orthanc/orthanc2.json`, change `DicomModalities` to:

```json
  "DicomModalities": {
    "ORTHANC1": ["ORTHANC1", "orthanc1", 7502],
    "ADIT": ["ADIT1DEV", "receiver", 11112],
    "ROUTER": ["ADIT1DEVROUTER", "router", 11112]
  },
```

- [ ] **Step 4: Document the env vars in `example.env`**

In the block `# Ports that will be mapped to the host during production.`, after
`RECEIVER_PORT=11112`, add:

```
ROUTER_PORT=11113
```

After the `RECEIVER_AE_TITLE=ADIT1DEV` line, add:

```

# The AE title of the DICOM router. A PACS forwards studies to this AE title.
# Leave empty to disable the router.
ROUTER_AE_TITLE=ADIT1DEVROUTER

# The host folder of the router spool, which holds identifiable images until they are
# routed. Defaults to a Docker volume; in production use a folder on an encrypted disk.
# ROUTER_SPOOL_DIR=./.docker-data/router-spool
```

Also add `ROUTER_AE_TITLE=ADIT1DEVROUTER` to your local `.env`; the dev stack reads `.env`, not
`example.env`.

- [ ] **Step 5: Register Orthanc 1 as a sender in the example data**

In `adit/core/management/commands/populate_example_data.py`, add the import
`from adit.router.models import RouterSender` next to the other `adit` imports. In
`create_server_nodes`, register the sender right after `orthanc1` is created:

```python
    orthanc1 = DicomServerFactory.create(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        host=settings.ORTHANC1_HOST,
        port=settings.ORTHANC1_DICOM_PORT,
    )
    grant_access(groups[0], orthanc1, source=True, destination=True)
    RouterSender.objects.create(server=orthanc1)
    servers.append(orthanc1)
```

- [ ] **Step 6: Update `CLAUDE.md`**

Under `# Management commands (run inside the web container)`, after the
`./manage.py receiver` line, add:

```
./manage.py router                         # Run the DICOM router (what the router container does)
```

Under `### Django Apps`, after the `**dicom_web/**` entry, add:

```
- **router/**: DICOM router inbox. `./manage.py router` (the router container) accepts C-STORE on `ROUTER_AE_TITLE` from enabled `RouterSender`s (a `DicomServer` plus the AE title it sends from, managed in the Django admin) and writes each image durably to `incoming/<sender id>/<StudyInstanceUID>/` in the spool (`ROUTER_SPOOL_PATH`). Unknown senders are rejected; while `RouterSettings.suspended` is set or the spool is low on space, images are answered with `0xA700`. Models: `RouterSettings`, `RouterSender`.
```

Replace the `**StoreScp**` line under `### DICOM Connectivity` with:

```
- **StoreScp** (`store_scp.py`): C-STORE SCP server, run by `./manage.py receiver` in the receiver container and by `./manage.py router` in the router container (with a calling-AE allow-list and its own store handler)
```

Under `### Docker Services`, after the `**receiver**` line, add:

```
- **router**: DICOM router C-STORE SCP (port 11112 internal; 11123 on host in dev, `ROUTER_PORT` in prod); spool in the `router_spool` volume or `ROUTER_SPOOL_DIR`; idles when `ROUTER_AE_TITLE` is empty
```

Under `## Environment Variables`, after the `RECEIVER_AE_TITLE` line, add:

```
- `ROUTER_AE_TITLE`: DICOM router AE title (empty disables the router; `example.env` uses `ADIT1DEVROUTER`). Also `ROUTER_PORT` (prod host port, default 11113), `ROUTER_SPOOL_DIR` (host folder of the spool, default a Docker volume), `ROUTER_SPOOL_MIN_FREE_GB` (images are refused below this free space, default 20), `ROUTER_SENDER_REFRESH_SECONDS` (default 30)
```

- [ ] **Step 7: Update the admin guide**

In `docs/user-docs/admin-guide.md`, in the "Optional tuning" paragraph, replace:

```
`ADIT_IMAGE` and `STACK_NAME` (a second stack such as staging on the same host).
```

with:

```
`ADIT_IMAGE` and `STACK_NAME` (a second stack such as staging on the same host), and `ROUTER_AE_TITLE`, `ROUTER_PORT` and `ROUTER_SPOOL_DIR` for the DICOM router (an empty `ROUTER_AE_TITLE` disables it; put the spool on an encrypted disk).
```

- [ ] **Step 8: Run the router end to end in the dev stack**

The dev web container only runs `populate_example_data` on an empty database, so register
the sender by hand in an existing dev database.

Run:

```bash
uv run cli compose-up -- --watch    # in a separate terminal; builds and starts the router
$COMPOSE restart orthanc1 orthanc2  # pick up the new ROUTER modality
$COMPOSE logs router | tail -5
```

Expected: the log contains `Store SCP server [ADIT1DEVROUTER] serving on 0.0.0.0:11112`.

Run:

```bash
$COMPOSE exec web python manage.py shell -c "
from adit.core.models import DicomServer
from adit.router.models import RouterSender
RouterSender.objects.get_or_create(server=DicomServer.objects.get(ae_title='ORTHANC1'))
"
sleep 35   # one sender refresh
$COMPOSE exec web bash -c '
  study=$(curl -s http://orthanc1.local:6501/studies | python -c "import json,sys; print(json.load(sys.stdin)[0])")
  curl -s -X POST http://orthanc1.local:6501/modalities/ROUTER/store -d "$study"'
$COMPOSE exec router find /spool/incoming -name "*.dcm" | head -3
```

Expected:
- Orthanc answers JSON with `"FailedInstancesCount" : 0` and an `"InstancesCount"` above 0.
- `find` lists files under `/spool/incoming/<sender id>/<StudyInstanceUID>/`.

Then disable the sender in the Django admin (Router senders), wait 35 s, and send again.

Expected: Orthanc reports the association as rejected, and no new files appear.

Clean up, since nothing reads the spool until stage 3:
`$COMPOSE exec router sh -c 'rm -rf /spool/incoming/*'`.

- [ ] **Step 9: Run the full suite and lint**

Run: `uv run cli test` and then `uv run cli lint`.

Expected: all tests pass, and lint reports no errors.

- [ ] **Step 10: Commit**

```bash
git add docker-compose.base.yml docker-compose.dev.yml docker-compose.prod.yml \
  orthanc/orthanc1.json orthanc/orthanc2.json example.env \
  adit/core/management/commands/populate_example_data.py CLAUDE.md docs/user-docs/admin-guide.md
git commit -m "Run the DICOM router as its own container"
```
