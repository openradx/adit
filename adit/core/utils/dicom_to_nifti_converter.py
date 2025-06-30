import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


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
            RuntimeError: If the conversion fails.
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
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to convert DICOM to NIfTI: {e.stderr.decode('utf-8')}")

        logger.debug(
            f"DICOM files in {dicom_folder} successfully converted to NIfTI format "
            f"in {output_folder}."
        )
