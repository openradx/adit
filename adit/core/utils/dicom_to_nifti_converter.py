import subprocess
from pathlib import Path
from typing import Union


class DicomToNiftiConverter:
    def __init__(self, dcm2niix_path: str = "dcm2niix"):
        """
        Initialize the converter with the path to the dcm2niix executable.
        :param dcm2niix_path: Path to the dcm2niix executable.
            Defaults to 'dcm2niix' if it's in PATH.
        """
        self.dcm2niix_path = dcm2niix_path

    def convert(self, dicom_folder: Union[str, Path], output_folder: Union[str, Path]) -> None:
        """
        Convert DICOM files in a folder to NIfTI format using dcm2niix.
        :param dicom_folder: Path to the folder containing DICOM files.
        :param output_folder: Path to the folder where NIfTI files will be saved.
        :raises RuntimeError: If the conversion fails.
        """
        dicom_folder = Path(dicom_folder)
        output_folder = Path(output_folder)

        if not dicom_folder.is_dir():
            raise ValueError(f"The specified DICOM folder does not exist: {dicom_folder}")
        if not output_folder.exists():
            output_folder.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.dcm2niix_path,
            "-z",
            "y",  # Compress output files
            "-o",
            str(output_folder),  # Output folder
            str(dicom_folder),  # Input folder
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to convert DICOM to NIfTI: {e.stderr.decode('utf-8')}")

        print(
            f"DICOM files in {dicom_folder} successfully converted to NIfTI format "
            f"in {output_folder}."
        )
