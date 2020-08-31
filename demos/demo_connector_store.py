import sys
from pathlib import Path

adit_root_path = Path(__file__).parent.parent.resolve()
sys.path.append(adit_root_path.as_posix())

# pylint: disable-msg=wrong-import-position
from adit.main.utils.dicom_connector import DicomConnector

config = DicomConnector.Config("ADIT", "ORTHANC2", "127.0.0.1", 7502)
connector = DicomConnector(config)

connector.open_connection()

dicom_path = adit_root_path / "samples" / "dicoms" / "10001"
connector.upload_folder(dicom_path)

connector.close_connection()
