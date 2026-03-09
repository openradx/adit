import logging
import subprocess
from unittest.mock import MagicMock

import pytest

from adit.core.errors import (
    DcmToNiftiConversionError,
    ExternalToolError,
    InputDirectoryError,
    InvalidDicomError,
    NoValidDicomError,
    OutputDirectoryError,
)
from adit.core.utils.dicom_to_nifti_converter import DicomToNiftiConverter

CONVERTER_LOGGER = "adit.core.utils.dicom_to_nifti_converter"


@pytest.fixture(autouse=True)
def _enable_log_propagation():
    """Enable propagation on the adit logger so caplog can capture log messages."""
    adit_logger = logging.getLogger("adit")
    original = adit_logger.propagate
    adit_logger.propagate = True
    yield
    adit_logger.propagate = original


def _make_completed_process(returncode: int, stdout: str = "", stderr: str = ""):
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.returncode = returncode
    mock.stdout = stdout.encode("utf-8")
    mock.stderr = stderr.encode("utf-8")
    return mock


class TestDicomToNiftiConverter:
    def test_convert_success(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        def fake_run(*args, **kwargs):
            output_folder.mkdir(parents=True, exist_ok=True)
            (output_folder / "output.nii").touch()
            return _make_completed_process(0)

        monkeypatch.setattr(subprocess, "run", fake_run)

        converter = DicomToNiftiConverter()
        converter.convert(dicom_folder, output_folder)

    def test_convert_no_dicom_found(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(2))

        converter = DicomToNiftiConverter()
        with pytest.raises(NoValidDicomError, match="No DICOM images found"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_corrupt_dicom(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(4))

        converter = DicomToNiftiConverter()
        with pytest.raises(InvalidDicomError, match="Corrupt DICOM"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_invalid_input_folder(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(5))

        converter = DicomToNiftiConverter()
        with pytest.raises(InputDirectoryError, match="Input folder invalid"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_invalid_output_folder(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(6))

        converter = DicomToNiftiConverter()
        with pytest.raises(OutputDirectoryError, match="Output folder invalid"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_write_permission_error(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(7))

        converter = DicomToNiftiConverter()
        with pytest.raises(OutputDirectoryError, match="Unable to write"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_partial_conversion(self, tmp_path, monkeypatch, caplog):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(8))

        converter = DicomToNiftiConverter()
        with caplog.at_level(logging.WARNING, logger=CONVERTER_LOGGER):
            converter.convert(dicom_folder, output_folder)

        assert any("Converted some but not all" in msg for msg in caplog.messages)

    def test_convert_rename_error(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(9))

        converter = DicomToNiftiConverter()
        with pytest.raises(DcmToNiftiConversionError, match="Unable to rename"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_unspecified_error(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _make_completed_process(1))

        converter = DicomToNiftiConverter()
        with pytest.raises(DcmToNiftiConversionError, match="Unspecified error"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_subprocess_error(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        def raise_subprocess_error(*args, **kwargs):
            raise subprocess.SubprocessError("dcm2niix not found")

        monkeypatch.setattr(subprocess, "run", raise_subprocess_error)

        converter = DicomToNiftiConverter()
        with pytest.raises(ExternalToolError, match="Failed to execute dcm2niix"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_nonexistent_dicom_folder(self, tmp_path):
        dicom_folder = tmp_path / "nonexistent"
        output_folder = tmp_path / "output"

        converter = DicomToNiftiConverter()
        with pytest.raises(ValueError, match="does not exist"):
            converter.convert(dicom_folder, output_folder)

    def test_convert_creates_output_folder_if_missing(self, tmp_path, monkeypatch):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output" / "nested"

        def fake_run(*args, **kwargs):
            output_folder.mkdir(parents=True, exist_ok=True)
            (output_folder / "output.nii").touch()
            return _make_completed_process(0)

        monkeypatch.setattr(subprocess, "run", fake_run)

        converter = DicomToNiftiConverter()
        converter.convert(dicom_folder, output_folder)

        assert output_folder.exists()

    def test_convert_logs_warning_on_dcm2niix_warnings(self, tmp_path, monkeypatch, caplog):
        dicom_folder = tmp_path / "dicom"
        dicom_folder.mkdir()
        output_folder = tmp_path / "output"

        def fake_run(*args, **kwargs):
            output_folder.mkdir(parents=True, exist_ok=True)
            (output_folder / "output.nii").touch()
            return _make_completed_process(0, stderr="Warning: some issue detected")

        monkeypatch.setattr(subprocess, "run", fake_run)

        converter = DicomToNiftiConverter()
        with caplog.at_level(logging.WARNING, logger=CONVERTER_LOGGER):
            converter.convert(dicom_folder, output_folder)

        assert any("Warnings during conversion" in msg for msg in caplog.messages)
