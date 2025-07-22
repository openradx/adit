import logging
import subprocess
from enum import IntEnum
from pathlib import Path

from adit.core.errors import (
    DicomConversionError,
    ExternalToolError,
    InputDirectoryError,
    InvalidDicomError,
    NoMemoryError,
    NoSpatialDataError,
    NoValidDicomError,
    OutputDirectoryError,
    UnknownFormatError,
)

logger = logging.getLogger(__name__)


class DcmExitCode(IntEnum):
    """Exit codes for dcm2niix as documented in https://github.com/rordenlab/dcm2niix/blob/master/ERRORS.md"""

    SUCCESS = 0
    MISSING_ARGUMENTS = 1
    OUTPUT_FOLDER_ERROR = 2
    INPUT_FOLDER_ERROR = 3
    INVALID_INPUT_FOLDER = 4
    UNKNOWN_FORMAT = 5
    CORRUPT_DICOM = 6
    NO_VALID_DICOM = 7
    NO_MEMORY = 8
    NO_SPATIAL_DATA = 9
    UNKNOWN_ERROR = 127


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
            NoSpatialDataError: If DICOM data doesn't contain spatial attributes.
            NoMemoryError: If the system runs out of memory during conversion.
            UnknownFormatError: If the input contains an unsupported format.
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
            elif exit_code == DcmExitCode.MISSING_ARGUMENTS:
                raise ExternalToolError(f"dcm2niix missing arguments: {error_msg}")
            elif exit_code == DcmExitCode.OUTPUT_FOLDER_ERROR:
                raise OutputDirectoryError(f"Error accessing output directory: {error_msg}")
            elif exit_code in (DcmExitCode.INPUT_FOLDER_ERROR, DcmExitCode.INVALID_INPUT_FOLDER):
                raise InputDirectoryError(f"Error accessing input directory: {error_msg}")
            elif exit_code == DcmExitCode.UNKNOWN_FORMAT:
                raise UnknownFormatError(f"Unknown or unsupported format: {error_msg}")
            elif exit_code == DcmExitCode.CORRUPT_DICOM:
                raise InvalidDicomError(f"Corrupt DICOM files: {error_msg}")
            elif exit_code == DcmExitCode.NO_VALID_DICOM:
                raise NoValidDicomError(f"No valid DICOM files found: {error_msg}")
            elif exit_code == DcmExitCode.NO_MEMORY:
                raise NoMemoryError(f"Not enough memory for conversion: {error_msg}")
            elif exit_code == DcmExitCode.NO_SPATIAL_DATA:
                raise NoSpatialDataError(f"No spatial attributes in DICOM data: {error_msg}")
            elif exit_code == DcmExitCode.UNKNOWN_ERROR or exit_code != 0:
                raise DicomConversionError(f"Unknown error (exit code {exit_code}): {error_msg}")

        except subprocess.SubprocessError as e:
            raise ExternalToolError(f"Failed to execute dcm2niix: {str(e)}")

        logger.debug(
            f"DICOM files in {dicom_folder} successfully converted to NIfTI format "
            f"in {output_folder}."
        )
