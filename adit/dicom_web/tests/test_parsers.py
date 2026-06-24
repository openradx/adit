"""Unit tests for the STOW-RS multipart parser in ``adit.dicom_web.parsers``.

These tests exercise the pure (non-DB, non-network) request-parsing plumbing:
multipart boundary handling, error paths for malformed requests and the
chunk-spanning streaming behaviour. Datasets are built fully in-memory so the
tests do not depend on any sample files or a running PACS.
"""

import io

import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from rest_framework.exceptions import NotAcceptable

from adit.core.utils.dicom_utils import write_dataset
from adit.dicom_web.parsers import _get_dicom_from_part, parse_request_in_chunks


def _make_dataset(sop_instance_uid: str = "1.2.3", patient_id: str = "P1") -> Dataset:
    """Build a minimal, writable DICOM dataset (with file meta)."""
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientName = "Doe^John"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"  # Secondary Capture
    ds.SOPInstanceUID = sop_instance_uid

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = file_meta
    ds.set_original_encoding(False, True)
    return ds


def _dicom_bytes(ds: Dataset) -> bytes:
    buffer = io.BytesIO()
    write_dataset(ds, buffer)
    return buffer.getvalue()


def _build_multipart_body(datasets: list[Dataset], boundary: str) -> bytes:
    """Assemble a ``multipart/related`` STOW-RS request body."""
    marker = b"--" + boundary.encode()
    body = b""
    for ds in datasets:
        body += marker + b"\r\n"
        body += b"Content-Type: application/dicom\r\n\r\n"
        body += _dicom_bytes(ds) + b"\r\n"
    body += marker + b"--\r\n"
    return body


class FakeRequest:
    """Minimal stand-in for an ``HttpRequest`` exposing ``content_type``/``read``."""

    def __init__(self, body: bytes, content_type: str | None) -> None:
        self._buffer = io.BytesIO(body)
        self.content_type = content_type

    def read(self, size: int) -> bytes:
        return self._buffer.read(size)


async def _collect(request: FakeRequest, **kwargs) -> list[Dataset]:
    results: list[Dataset] = []
    async for ds in parse_request_in_chunks(request, **kwargs):
        results.append(ds)
    return results


def _content_type(boundary: str, quoted: bool = False) -> str:
    value = f'"{boundary}"' if quoted else boundary
    return f"multipart/related; type=application/dicom; boundary={value}"


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parses_single_part():
    ds = _make_dataset("1.2.3")
    body = _build_multipart_body([ds], "myboundary")
    request = FakeRequest(body, _content_type("myboundary"))

    results = await _collect(request)

    assert len(results) == 1
    assert str(results[0].SOPInstanceUID) == "1.2.3"
    assert results[0].PatientID == "P1"


@pytest.mark.asyncio
async def test_parses_multiple_parts():
    """Several parts sharing a single chunk read must all be parsed.

    Regression guard for the bug where the parser split on only the first
    boundary per read, silently dropping the 2nd+ parts.
    """
    datasets = [_make_dataset(f"1.2.{i}") for i in range(3)]
    body = _build_multipart_body(datasets, "B")
    request = FakeRequest(body, _content_type("B"))

    results = await _collect(request)

    assert [str(ds.SOPInstanceUID) for ds in results] == ["1.2.0", "1.2.1", "1.2.2"]


@pytest.mark.asyncio
async def test_parses_multiple_parts_with_small_chunks():
    """With each part landing in its own chunk read, all parts are parsed.

    This is the same scenario as ``test_parses_multiple_parts`` but with a
    ``chunk_size`` small enough that no two boundaries share a single read,
    which avoids the single-boundary-per-chunk bug. It documents that the
    multipart assembly itself is correct; only the chunk-spanning split is not.
    """
    datasets = [_make_dataset(f"1.2.{i}") for i in range(3)]
    body = _build_multipart_body(datasets, "B")
    request = FakeRequest(body, _content_type("B"))

    results = await _collect(request, chunk_size=64)

    assert [str(ds.SOPInstanceUID) for ds in results] == ["1.2.0", "1.2.1", "1.2.2"]


@pytest.mark.asyncio
async def test_parses_quoted_boundary():
    ds = _make_dataset("9.9.9")
    body = _build_multipart_body([ds], "quoted-boundary")
    # boundary value wrapped in double quotes (the parser strips them).
    request = FakeRequest(body, _content_type("quoted-boundary", quoted=True))

    results = await _collect(request)

    assert len(results) == 1
    assert str(results[0].SOPInstanceUID) == "9.9.9"


@pytest.mark.asyncio
async def test_streaming_across_small_chunks():
    """A boundary split across several ``read`` calls must still be detected."""
    ds = _make_dataset("4.5.6")
    body = _build_multipart_body([ds], "B")
    request = FakeRequest(body, _content_type("B"))

    # chunk_size of 7 forces the boundary to span multiple reads.
    results = await _collect(request, chunk_size=7)

    assert len(results) == 1
    assert str(results[0].SOPInstanceUID) == "4.5.6"


@pytest.mark.asyncio
async def test_empty_multipart_body_yields_nothing():
    """A body with only the closing boundary yields no datasets (no crash)."""
    body = b"--B--\r\n"
    request = FakeRequest(body, _content_type("B"))

    results = await _collect(request)

    assert results == []


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_boundary_raises_not_acceptable():
    request = FakeRequest(b"whatever", "multipart/related")

    with pytest.raises(NotAcceptable):
        await _collect(request)


@pytest.mark.asyncio
async def test_missing_content_type_raises_not_acceptable():
    # content_type is None -> the assert is caught and re-raised as NotAcceptable.
    request = FakeRequest(b"whatever", None)

    with pytest.raises(NotAcceptable):
        await _collect(request)


@pytest.mark.asyncio
async def test_content_type_without_boundary_keyword_raises_not_acceptable():
    request = FakeRequest(b"data", "application/dicom")

    with pytest.raises(NotAcceptable):
        await _collect(request)


# ---------------------------------------------------------------------------
# _get_dicom_from_part: sentinel / boundary-marker handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("part", [b"", b"--", b"\r\n", b"--\r\n", b"--\r\nepilogue"])
async def test_get_dicom_from_part_ignores_sentinels(part):
    """Empty parts and boundary markers must be skipped (return None)."""
    assert await _get_dicom_from_part(part) is None
