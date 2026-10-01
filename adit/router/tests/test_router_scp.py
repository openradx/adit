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
