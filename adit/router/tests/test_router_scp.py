import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom.data import get_testdata_file
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, JPEGLosslessSV1, generate_uid
from pynetdicom import AE
from pynetdicom.association import Association
from pynetdicom.sop_class import Verification  # pyright: ignore

from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.store_scp import StoreScp
from adit.core.utils.testing_helpers import free_port, wait_until_scp_accepts, wait_until_scp_idle
from adit.router.utils import spool
from adit.router.utils.intake import IntakeConfig, RouterStoreHandler, build_router_scp

ROUTER_AE = "ROUTERTEST"


@dataclass
class Router:
    scp: StoreScp
    handler: RouterStoreHandler
    port: int
    spool_root: Path


@pytest.fixture
def router(tmp_path: Path) -> Iterator[Router]:
    spool.ensure_spool_dirs(tmp_path)
    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)
    handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=False))
    port = free_port()
    scp = build_router_scp(tmp_path, handler, ae_title=ROUTER_AE, host="127.0.0.1", port=port)
    thread = threading.Thread(target=scp.start, daemon=True)
    thread.start()
    wait_until_scp_accepts(port, "PACS1", ROUTER_AE)
    yield Router(scp, handler, port, tmp_path)
    wait_until_scp_idle(scp)
    scp.stop()
    thread.join(timeout=5)


def _associate(
    port: int,
    calling_ae: str,
    called_ae: str = ROUTER_AE,
    sop_class: str = CTImageStorage,
    transfer_syntax: str = ExplicitVRLittleEndian,
) -> Association:
    ae = AE(ae_title=calling_ae)
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.add_requested_context(sop_class, transfer_syntax)
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


def test_known_sender_can_verify_the_connection(router):
    """PACS administrators run a C-ECHO when they add the router as a destination."""
    assoc = _associate(router.port, "PACS1", sop_class=Verification)
    assert assoc.is_established

    status = assoc.send_c_echo()
    assoc.release()

    assert status.Status == 0x0000


def test_no_enabled_sender_refuses_every_association(router):
    router.scp.set_allowed_calling_aets([])

    assoc = _associate(router.port, "PACS1")

    assert assoc.is_rejected


def test_compressed_images_are_accepted_as_sent(router):
    """Many PACS store and forward JPEG Lossless; the router accepts it unchanged."""
    assoc = _associate(router.port, "PACS1", transfer_syntax=JPEGLosslessSV1)
    assert assoc.is_established

    accepted = [str(cx.transfer_syntax[0]) for cx in assoc.accepted_contexts]
    assoc.release()

    assert accepted == [JPEGLosslessSV1]


def test_compressed_image_is_stored_as_sent(router):
    original = get_testdata_file("MR_small_jpeg_ls_lossless.dcm", read=True)
    assert isinstance(original, Dataset)
    assoc = _associate(
        router.port,
        "PACS1",
        sop_class=original.SOPClassUID,
        transfer_syntax=original.file_meta.TransferSyntaxUID,
    )
    assert assoc.is_established

    status = assoc.send_c_store(original)
    assoc.release()

    assert status.Status == 0x0000
    study_dir = router.spool_root / spool.INCOMING / "7" / original.StudyInstanceUID
    spooled = read_dataset(study_dir / f"{original.SOPInstanceUID}.dcm")
    assert spooled.file_meta.TransferSyntaxUID == original.file_meta.TransferSyntaxUID
    assert spooled.PixelData == original.PixelData


def test_suspended_router_answers_out_of_resources(router):
    router.handler.update_config(IntakeConfig(sender_ids={"PACS1": 7}, suspended=True))
    assoc = _associate(router.port, "PACS1")

    status = assoc.send_c_store(_ct_image())
    assoc.release()

    assert status.Status == 0xA700
    assert list((router.spool_root / spool.INCOMING).rglob("*.dcm")) == []
