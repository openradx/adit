import logging
import subprocess
from enum import IntEnum
from pathlib import Path

from adit.core.errors import (
    DicomConversionError,
    ExternalToolError,
    InputDirectoryError,
    InvalidDicomError,
    NoValidDicomError,
    OutputDirectoryError,
)

logger = logging.getLogger(__name__)


class DcmExitCode(IntEnum):
    """Exit codes for dcm2niix as documented in https://github.com/rordenlab/dcm2niix"""

    SUCCESS = 0
    UNSPECIFIED_ERROR = 1
    NO_DICOM_FOUND = 2
    VERSION_REPORT = 3
    CORRUPT_DICOM = 4
    INVALID_INPUT_FOLDER = 5
    INVALID_OUTPUT_FOLDER = 6
    WRITE_PERMISSION_ERROR = 7
    PARTIAL_CONVERSION = 8
    RENAME_ERROR = 9
    UNKNOWN_ERROR = 127  # Kept for backward compatibility


class DicomToNiftiConverter:
    def __init__(self, dcm2niix_path: str = "dcm2niix"):
        """Initialize the converter with the path to the dcm2niix executable.

        Args:
            dcm2niix_path: Path to the dcm2niix executable.
                Defaults to 'dcm2niix' if it's in PATH.
        """
        self.dcm2niix_path = dcm2niix_path

    def convert(self, dicom_folder: str | Path, output_folder: str | Path) -> None:
        """Convert DICOM files in a folder to NIfTI format using dcm2niix.

        Args:
            dicom_folder: Path to the folder containing DICOM files.
            output_folder: Path to the folder where NIfTI files will be saved.
        Raises:
            ValueError: If the dicom_folder doesn't exist.
            NoValidDicomError: If no valid DICOM files are found.
            InvalidDicomError: If DICOM files are invalid or corrupt.
            OutputDirectoryError: If there are issues with the output directory.
            InputDirectoryError: If there are issues with the input directory.
            ExternalToolError: If there are issues with the dcm2niix tool.
            DicomConversionError: For other conversion errors.
        """
        dicom_folder = Path(dicom_folder)
        output_folder = Path(output_folder)

        if not dicom_folder.is_dir():
            raise ValueError(f"The specified DICOM folder does not exist: {dicom_folder}")

        if not output_folder.exists():
            output_folder.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.dcm2niix_path,
            "-f",
            "%s-%d",
            "-z",
            "y",
            "-o",
            str(output_folder),
            str(dicom_folder),
        ]

        try:
            result = subprocess.run(
                cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stderr = result.stderr.decode("utf-8")
            stdout = result.stdout.decode("utf-8")

            # Check for warnings in the output
            if "Warning:" in stderr or "Warning:" in stdout:
                logger.warning(f"Warnings during conversion: {stderr}\n{stdout}")

            # Check exit code and raise appropriate exception
            exit_code = result.returncode
            error_msg = f"{stderr}\n{stdout}".strip()

            if exit_code == DcmExitCode.SUCCESS:
                pass  # Successful conversion
            elif exit_code == DcmExitCode.NO_DICOM_FOUND:
                raise NoValidDicomError(f"No DICOM images found in input folder: {error_msg}")
            elif exit_code == DcmExitCode.VERSION_REPORT:
                logger.info(f"dcm2niix version report: {error_msg}")
            elif exit_code == DcmExitCode.CORRUPT_DICOM:
                raise InvalidDicomError(f"Corrupt DICOM file: {error_msg}")
            elif exit_code == DcmExitCode.INVALID_INPUT_FOLDER:
                raise InputDirectoryError(f"Input folder invalid: {error_msg}")
            elif exit_code == DcmExitCode.INVALID_OUTPUT_FOLDER:
                raise OutputDirectoryError(f"Output folder invalid: {error_msg}")
            elif exit_code == DcmExitCode.WRITE_PERMISSION_ERROR:
                raise OutputDirectoryError(
                    f"Unable to write to output folder (check permissions): {error_msg}"
                )
            elif exit_code == DcmExitCode.PARTIAL_CONVERSION:
                logger.warning(f"Converted some but not all input DICOMs: {error_msg}")
            elif exit_code == DcmExitCode.RENAME_ERROR:
                raise DicomConversionError(f"Unable to rename files: {error_msg}")
            elif exit_code == DcmExitCode.UNSPECIFIED_ERROR or exit_code != 0:
                raise DicomConversionError(
                    f"Unspecified error (exit code {exit_code}): {error_msg}"
                )

        except subprocess.SubprocessError as e:
            raise ExternalToolError(f"Failed to execute dcm2niix: {e}")

        logger.debug(
            f"DICOM files in {dicom_folder} successfully converted to NIfTI format "
            f"in {output_folder}."
        )
