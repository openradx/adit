"""Unit tests for the DICOMweb response renderers in ``adit.dicom_web.renderers``.

Covers the WADO-RS NIfTI multipart renderer, QIDO-RS JSON shaping, STOW-RS JSON
shaping (single vs. list), WADO-RS JSON metadata extraction and the WADO-RS
``multipart/related`` streaming output (instance frames, the trailing end
boundary, and the error stream). None of these touch the database or a PACS.
"""

import io
import json
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from adit.dicom_web.renderers import (
    DicomWebWadoRenderer,
    QidoApplicationDicomJsonRenderer,
    StowApplicationDicomJsonRenderer,
    WadoApplicationDicomJsonRenderer,
    WadoMultipartApplicationDicomRenderer,
    WadoMultipartApplicationNiftiRenderer,
)


async def _collect_rendered_output(renderer, images):
    chunks = []
    async for chunk in renderer.render(images):
        chunks.append(chunk)
    return b"".join(chunks)


async def _async_iter(items):
    for item in items:
        yield item


class TestWadoMultipartApplicationNiftiRenderer:
    @pytest.mark.asyncio
    async def test_render_single_file(self):
        renderer = WadoMultipartApplicationNiftiRenderer()
        content = b"fake nifti data"
        files = [("scan.nii.gz", BytesIO(content))]

        output = await _collect_rendered_output(renderer, _async_iter(files))

        assert b"--nifti-boundary\r\n" in output
        assert b"Content-Type: application/octet-stream\r\n" in output
        assert b'Content-Disposition: attachment; filename="scan.nii.gz"' in output
        assert content in output
        assert output.endswith(b"\r\n--nifti-boundary--\r\n")

    @pytest.mark.asyncio
    async def test_render_multiple_files(self):
        renderer = WadoMultipartApplicationNiftiRenderer()
        files = [
            ("scan.json", BytesIO(b'{"key": "value"}')),
            ("scan.nii.gz", BytesIO(b"nifti data")),
        ]

        output = await _collect_rendered_output(renderer, _async_iter(files))

        # First file starts without leading \r\n
        assert output.startswith(b"--nifti-boundary\r\n")
        # Second file separated by \r\n--boundary\r\n
        assert b"\r\n--nifti-boundary\r\n" in output
        # Both filenames present
        assert b'filename="scan.json"' in output
        assert b'filename="scan.nii.gz"' in output
        assert output.endswith(b"\r\n--nifti-boundary--\r\n")

    @pytest.mark.asyncio
    async def test_render_empty_iterator(self):
        renderer = WadoMultipartApplicationNiftiRenderer()

        output = await _collect_rendered_output(renderer, _async_iter([]))

        # Empty iterator produces no output — no parts, no boundary
        assert output == b""

    @pytest.mark.asyncio
    async def test_render_filename_sanitization(self):
        renderer = WadoMultipartApplicationNiftiRenderer()
        malicious_name = 'bad\r\nname"file.nii.gz'
        files = [(malicious_name, BytesIO(b"data"))]

        output = await _collect_rendered_output(renderer, _async_iter(files))

        # \r, \n, and " should be stripped
        assert b'filename="badnamefile.nii.gz"' in output
        assert b"\r\nname" not in output.split(b"Content-Disposition")[1].split(b"\r\n\r\n")[0]

    def test_content_type_property(self):
        renderer = WadoMultipartApplicationNiftiRenderer()

        assert renderer.content_type == (
            "multipart/related; type=application/octet-stream; boundary=nifti-boundary"
        )


def _make_dataset(sop_instance_uid: str = "1.2.3") -> Dataset:
    ds = Dataset()
    ds.PatientID = "P1"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.SOPInstanceUID = sop_instance_uid

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = file_meta
    ds.set_original_encoding(False, True)
    return ds


# ---------------------------------------------------------------------------
# QIDO-RS renderer
# ---------------------------------------------------------------------------


def test_qido_renderer_serializes_list_to_json():
    renderer = QidoApplicationDicomJsonRenderer()
    data = [{"00100020": {"vr": "LO", "Value": ["P1"]}}]

    rendered = renderer.render(data)

    assert isinstance(rendered, str)
    assert json.loads(rendered) == data


def test_qido_renderer_media_type():
    assert QidoApplicationDicomJsonRenderer.media_type == "application/dicom+json"
    assert QidoApplicationDicomJsonRenderer.format == "json"


# ---------------------------------------------------------------------------
# STOW-RS renderer
# ---------------------------------------------------------------------------


def test_stow_renderer_single_result_is_object():
    """A single stored instance is rendered as a JSON object (not a list)."""
    renderer = StowApplicationDicomJsonRenderer()
    ds = _make_dataset("1.2.3")

    rendered = renderer.render([ds])
    parsed = json.loads(rendered)

    assert isinstance(parsed, dict)
    assert parsed == ds.to_json_dict()


def test_stow_renderer_multiple_results_is_list():
    renderer = StowApplicationDicomJsonRenderer()
    datasets = [_make_dataset("1.2.3"), _make_dataset("4.5.6")]

    rendered = renderer.render(datasets)
    parsed = json.loads(rendered)

    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_stow_renderer_empty_results_is_empty_list():
    renderer = StowApplicationDicomJsonRenderer()

    assert json.loads(renderer.render([])) == []


# ---------------------------------------------------------------------------
# WADO-RS JSON renderer
# ---------------------------------------------------------------------------


def test_wado_json_renderer_extracts_metadata():
    renderer = WadoApplicationDicomJsonRenderer()
    metadata = [{"00080018": {"vr": "UI", "Value": ["1.2.3"]}}]

    rendered = renderer.render({"metadata": metadata})

    assert json.loads(rendered) == metadata


# ---------------------------------------------------------------------------
# DicomWebWadoRenderer.content_type property
# ---------------------------------------------------------------------------


def test_content_type_includes_boundary_and_charset():
    renderer = WadoMultipartApplicationDicomRenderer()
    content_type = renderer.content_type

    assert content_type.startswith("multipart/related")
    assert "boundary=adit-boundary" in content_type
    assert "charset=utf-8" in content_type


def test_content_type_duplicates_type_parameter():
    """Documents a minor quirk: ``type=application/dicom`` appears twice.

    ``media_type`` already contains ``; type=application/dicom`` and the
    ``content_type`` property appends ``subtype`` again, yielding a duplicated
    ``type=`` parameter. Asserted here so the behaviour is pinned; it is
    cosmetic (the value is identical both times).
    """
    content_type = WadoMultipartApplicationDicomRenderer().content_type

    assert content_type.count("type=application/dicom") == 2


def test_content_type_minimal_without_subtype_or_boundary():
    """With only ``media_type`` set, no ``type=`` / ``boundary=`` params appear.

    Note: ``charset`` IS still appended because DRF's ``BaseRenderer`` defines a
    default ``charset = "utf-8"`` class attribute, so ``hasattr(self, "charset")``
    is always truthy even on a subclass that never sets it itself.
    """

    class _Bare(DicomWebWadoRenderer):
        media_type = "application/dicom"

    content_type = _Bare().content_type
    assert content_type.startswith("application/dicom")
    assert "type=" not in content_type
    assert "boundary=" not in content_type
    assert "charset=utf-8" in content_type


# ---------------------------------------------------------------------------
# WADO-RS multipart streaming renderer
# ---------------------------------------------------------------------------


async def _aiter(datasets: list[Dataset]) -> AsyncIterator[Dataset]:
    for ds in datasets:
        yield ds


async def _collect_stream(renderer, images: AsyncIterator[Dataset]) -> list[bytes]:
    chunks: list[bytes] = []
    async for chunk in renderer.render(images):
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_multipart_stream_single_instance():
    renderer = WadoMultipartApplicationDicomRenderer()
    ds = _make_dataset("1.2.3")

    chunks = await _collect_stream(renderer, _aiter([ds]))

    # One instance chunk + the trailing end-boundary chunk.
    assert len(chunks) == 2
    instance_chunk = chunks[0]
    assert instance_chunk.startswith(b"\r\n--adit-boundary\r\n")
    assert b"Content-Type: application/dicom" in instance_chunk
    assert chunks[-1] == b"--adit-boundary--"


@pytest.mark.asyncio
async def test_multipart_stream_multiple_instances():
    renderer = WadoMultipartApplicationDicomRenderer()
    datasets = [_make_dataset(f"1.2.{i}") for i in range(3)]

    chunks = await _collect_stream(renderer, _aiter(datasets))

    # Three instance chunks + the trailing end-boundary chunk.
    assert len(chunks) == 4
    assert all(c.startswith(b"\r\n--adit-boundary\r\n") for c in chunks[:-1])
    assert chunks[-1] == b"--adit-boundary--"


@pytest.mark.asyncio
async def test_multipart_stream_round_trips_instance():
    """The DICOM payload embedded in a part must be readable back."""
    from adit.core.utils.dicom_utils import read_dataset

    renderer = WadoMultipartApplicationDicomRenderer()
    ds = _make_dataset("7.8.9")

    chunks = await _collect_stream(renderer, _aiter([ds]))

    part = chunks[0]
    payload = part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n")
    parsed = read_dataset(io.BytesIO(payload))
    assert str(parsed.SOPInstanceUID) == "7.8.9"


@pytest.mark.asyncio
async def test_multipart_stream_emits_error_part_on_exception():
    """An exception while iterating images yields a text/plain error part."""
    renderer = WadoMultipartApplicationDicomRenderer()

    async def _boom() -> AsyncIterator[Dataset]:
        raise RuntimeError("kaboom")
        yield  # pragma: no cover - makes this an async generator

    chunks = await _collect_stream(renderer, _boom())

    error_chunk = chunks[0]
    assert b"Content-Type: text/plain" in error_chunk
    assert b"Failed to fetch DICOM data" in error_chunk
    assert b"kaboom" in error_chunk
    # The stream is still terminated with the end boundary.
    assert chunks[-1] == b"--adit-boundary--"
