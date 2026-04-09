import asyncio
import logging
from io import BytesIO
from typing import cast
from unittest.mock import MagicMock

import pytest
from pydicom import Dataset

from adit.core.errors import (
    DcmToNiftiConversionError,
    DicomError,
    NoSpatialDataError,
    NoValidDicomError,
    RetriableDicomError,
)
from adit.core.models import DicomServer
from adit.dicom_web.errors import BadGatewayApiError, ServiceUnavailableApiError
from adit.dicom_web.utils import wadors_utils

WADORS_LOGGER = "adit.dicom_web.utils.wadors_utils"


@pytest.fixture(autouse=True)
def _enable_log_propagation():
    """Enable propagation on the adit logger so caplog can capture log messages."""
    adit_logger = logging.getLogger("adit")
    original = adit_logger.propagate
    adit_logger.propagate = True
    yield
    adit_logger.propagate = original


# --- Fakes reused across tests (following test_wado_retrieve.py pattern) ---


class FakeDicomServer:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        for attr in [
            "patient_root_find_support",
            "patient_root_get_support",
            "patient_root_move_support",
            "study_root_find_support",
            "study_root_get_support",
            "study_root_move_support",
            "store_scp_support",
        ]:
            if not hasattr(self, attr):
                setattr(self, attr, False)


def _make_server() -> DicomServer:
    return cast(
        DicomServer, FakeDicomServer(name="Test", ae_title="TEST", host="localhost", port=104)
    )


def immediate_sync_to_async(func, *, thread_sensitive=False):
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    return wrapper


def _make_series_dataset(series_uid: str, modality: str) -> Dataset:
    ds = Dataset()
    ds.SeriesInstanceUID = series_uid
    ds.Modality = modality
    return ds


# --- wado_retrieve_nifti tests ---


class TestWadoRetrieveNifti:
    @pytest.mark.asyncio
    async def test_study_filters_non_image_modalities(self, monkeypatch):
        """SR, KO, PR series should be skipped; CT series should be processed."""
        series_list = [
            _make_series_dataset("1.1", "CT"),
            _make_series_dataset("1.2", "SR"),
            _make_series_dataset("1.3", "KO"),
            _make_series_dataset("1.4", "PR"),
        ]
        fetched_series_uids = []

        class FakeOperator:
            def __init__(self, server):
                pass

            def find_series(self, query_ds):
                return series_list

        def fake_fetch_dicom_data(source_server, query, level):
            fetched_series_uids.append(query["SeriesInstanceUID"])
            return [Dataset()]

        async def fake_process_single_fetch(dicom_images):
            yield ("test.nii.gz", BytesIO(b"nifti"))

        monkeypatch.setattr(wadors_utils, "DicomOperator", FakeOperator)
        monkeypatch.setattr(wadors_utils, "_fetch_dicom_data", fake_fetch_dicom_data)
        monkeypatch.setattr(wadors_utils, "_process_single_fetch", fake_process_single_fetch)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        query = {"PatientID": "P1", "StudyInstanceUID": "1.2.3"}
        results = []
        async for item in wadors_utils.wado_retrieve_nifti(_make_server(), query, "STUDY"):
            results.append(item)

        # Only the CT series should have been fetched
        assert fetched_series_uids == ["1.1"]
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_study_all_non_image_modalities(self, monkeypatch):
        """Study with only SR/KO/PR series should yield nothing."""
        series_list = [
            _make_series_dataset("1.1", "SR"),
            _make_series_dataset("1.2", "KO"),
        ]

        class FakeOperator:
            def __init__(self, server):
                pass

            def find_series(self, query_ds):
                return series_list

        monkeypatch.setattr(wadors_utils, "DicomOperator", FakeOperator)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        query = {"PatientID": "P1", "StudyInstanceUID": "1.2.3"}
        results = []
        async for item in wadors_utils.wado_retrieve_nifti(_make_server(), query, "STUDY"):
            results.append(item)

        assert results == []

    @pytest.mark.asyncio
    async def test_series_level(self, monkeypatch):
        """Series-level should fetch directly without modality filtering."""

        def fake_fetch_dicom_data(source_server, query, level):
            assert level == "SERIES"
            return [Dataset()]

        async def fake_process_single_fetch(dicom_images):
            yield ("series.nii.gz", BytesIO(b"data"))

        monkeypatch.setattr(wadors_utils, "DicomOperator", lambda s: None)
        monkeypatch.setattr(wadors_utils, "_fetch_dicom_data", fake_fetch_dicom_data)
        monkeypatch.setattr(wadors_utils, "_process_single_fetch", fake_process_single_fetch)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        query = {
            "PatientID": "P1",
            "StudyInstanceUID": "1.2.3",
            "SeriesInstanceUID": "1.2.3.4",
        }
        results = []
        async for item in wadors_utils.wado_retrieve_nifti(_make_server(), query, "SERIES"):
            results.append(item)

        assert len(results) == 1
        assert results[0][0] == "series.nii.gz"

    @pytest.mark.asyncio
    async def test_image_level(self, monkeypatch):
        """Image-level should fetch directly without modality filtering."""

        def fake_fetch_dicom_data(source_server, query, level):
            assert level == "IMAGE"
            return [Dataset()]

        async def fake_process_single_fetch(dicom_images):
            yield ("image.nii.gz", BytesIO(b"data"))

        monkeypatch.setattr(wadors_utils, "DicomOperator", lambda s: None)
        monkeypatch.setattr(wadors_utils, "_fetch_dicom_data", fake_fetch_dicom_data)
        monkeypatch.setattr(wadors_utils, "_process_single_fetch", fake_process_single_fetch)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        query = {
            "PatientID": "P1",
            "StudyInstanceUID": "1.2.3",
            "SeriesInstanceUID": "1.2.3.4",
            "SOPInstanceUID": "1.2.3.4.5",
        }
        results = []
        async for item in wadors_utils.wado_retrieve_nifti(_make_server(), query, "IMAGE"):
            results.append(item)

        assert len(results) == 1
        assert results[0][0] == "image.nii.gz"

    @pytest.mark.asyncio
    async def test_retriable_error(self, monkeypatch):
        """RetriableDicomError should be wrapped as ServiceUnavailableApiError."""

        def fake_fetch_dicom_data(source_server, query, level):
            raise RetriableDicomError("timeout")

        monkeypatch.setattr(wadors_utils, "DicomOperator", lambda s: None)
        monkeypatch.setattr(wadors_utils, "_fetch_dicom_data", fake_fetch_dicom_data)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        query = {
            "PatientID": "P1",
            "StudyInstanceUID": "1.2.3",
            "SeriesInstanceUID": "1.2.3.4",
        }

        with pytest.raises(ServiceUnavailableApiError):
            async for _ in wadors_utils.wado_retrieve_nifti(_make_server(), query, "SERIES"):
                pass

    @pytest.mark.asyncio
    async def test_non_retriable_error(self, monkeypatch):
        """DicomError should be wrapped as BadGatewayApiError."""

        def fake_fetch_dicom_data(source_server, query, level):
            raise DicomError("permanent failure")

        monkeypatch.setattr(wadors_utils, "DicomOperator", lambda s: None)
        monkeypatch.setattr(wadors_utils, "_fetch_dicom_data", fake_fetch_dicom_data)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        query = {
            "PatientID": "P1",
            "StudyInstanceUID": "1.2.3",
            "SeriesInstanceUID": "1.2.3.4",
        }

        with pytest.raises(BadGatewayApiError):
            async for _ in wadors_utils.wado_retrieve_nifti(_make_server(), query, "SERIES"):
                pass


# --- _process_single_fetch tests ---


class TestProcessSingleFetch:
    @pytest.mark.asyncio
    async def test_yields_files_in_order(self, tmp_path, monkeypatch):
        """Files should be yielded in order: json, nifti, bval, bvec."""
        nifti_output_dir = tmp_path / "nifti_output"
        nifti_output_dir.mkdir()

        # Create fake output files
        (nifti_output_dir / "scan.json").write_text('{"key": "val"}')
        (nifti_output_dir / "scan.nii.gz").write_bytes(b"nifti data")
        (nifti_output_dir / "scan.bval").write_text("0 1000")
        (nifti_output_dir / "scan.bvec").write_text("1 0 0")

        monkeypatch.setattr(
            wadors_utils, "DicomToNiftiConverter", lambda: MagicMock(convert=MagicMock())
        )
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        # Patch TemporaryDirectory to use our tmp_path
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        ds = Dataset()
        ds.PatientID = "P1"
        results = []
        async for filename, content in wadors_utils._process_single_fetch([ds]):
            results.append((filename, content.read()))

        filenames = [r[0] for r in results]
        assert filenames == ["scan.json", "scan.nii.gz", "scan.bval", "scan.bvec"]

    @pytest.mark.asyncio
    async def test_handles_nii_without_gz(self, tmp_path, monkeypatch):
        """Uncompressed .nii files should also be yielded."""
        nifti_output_dir = tmp_path / "nifti_output"
        nifti_output_dir.mkdir()
        (nifti_output_dir / "scan.nii").write_bytes(b"nifti data")

        monkeypatch.setattr(
            wadors_utils, "DicomToNiftiConverter", lambda: MagicMock(convert=MagicMock())
        )
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        results = []
        async for filename, content in wadors_utils._process_single_fetch([Dataset()]):
            results.append(filename)

        assert results == ["scan.nii"]

    @pytest.mark.asyncio
    async def test_no_valid_dicom_logs_warning(self, tmp_path, monkeypatch, caplog):
        """NoValidDicomError should log a warning and yield nothing."""
        converter_mock = MagicMock()
        converter_mock.convert.side_effect = NoValidDicomError("no dicom")

        monkeypatch.setattr(wadors_utils, "DicomToNiftiConverter", lambda: converter_mock)
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        results = []
        with caplog.at_level(logging.WARNING, logger=WADORS_LOGGER):
            async for item in wadors_utils._process_single_fetch([Dataset()]):
                results.append(item)

        assert results == []
        assert any("conversion failed unexpectedly" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_no_spatial_data_logs_warning(self, tmp_path, monkeypatch, caplog):
        """NoSpatialDataError should log a warning and yield nothing."""
        converter_mock = MagicMock()
        converter_mock.convert.side_effect = NoSpatialDataError("no spatial")

        monkeypatch.setattr(wadors_utils, "DicomToNiftiConverter", lambda: converter_mock)
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        results = []
        with caplog.at_level(logging.WARNING, logger=WADORS_LOGGER):
            async for item in wadors_utils._process_single_fetch([Dataset()]):
                results.append(item)

        assert results == []
        assert any("conversion failed unexpectedly" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_conversion_error_propagates(self, tmp_path, monkeypatch):
        """DcmToNiftiConversionError should propagate to the caller."""
        converter_mock = MagicMock()
        converter_mock.convert.side_effect = DcmToNiftiConversionError("convert failed")

        monkeypatch.setattr(wadors_utils, "DicomToNiftiConverter", lambda: converter_mock)
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        with pytest.raises(DcmToNiftiConversionError, match="convert failed"):
            async for _ in wadors_utils._process_single_fetch([Dataset()]):
                pass

    @pytest.mark.asyncio
    async def test_unexpected_error_propagates(self, tmp_path, monkeypatch):
        """Generic exceptions should be re-raised."""
        converter_mock = MagicMock()
        converter_mock.convert.side_effect = RuntimeError("unexpected")

        monkeypatch.setattr(wadors_utils, "DicomToNiftiConverter", lambda: converter_mock)
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        with pytest.raises(RuntimeError, match="unexpected"):
            async for _ in wadors_utils._process_single_fetch([Dataset()]):
                pass

    @pytest.mark.asyncio
    async def test_empty_dicom_list(self, tmp_path, monkeypatch):
        """Empty dicom list should still attempt conversion (dcm2niix handles it)."""
        nifti_output_dir = tmp_path / "nifti_output"
        nifti_output_dir.mkdir()

        converter_mock = MagicMock()
        converter_mock.convert.side_effect = NoValidDicomError("no dicom")

        monkeypatch.setattr(wadors_utils, "DicomToNiftiConverter", lambda: converter_mock)
        monkeypatch.setattr(wadors_utils, "write_dataset", lambda ds, path: None)
        monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_temp_dir():
            yield str(tmp_path)

        monkeypatch.setattr(wadors_utils, "TemporaryDirectory", fake_temp_dir)

        results = []
        async for item in wadors_utils._process_single_fetch([]):
            results.append(item)

        assert results == []
