import sys
from pathlib import Path
from pprint import pprint

path = Path(__file__).parent.parent.resolve()
sys.path.append(path.as_posix())

# pylint: disable-msg=wrong-import-position
from adit.main.utils.dicom_connector import DicomConnector

config = DicomConnector.Config(
    "ADIT", "ORTHANC1", "127.0.0.1", 7501, patient_root_query_model_get=False
)
connector = DicomConnector(config)

connector.open_connection()

query_dict = {
    "QueryRetrieveLevel": "STUDY",
    "PatientID": "10001",
    "StudyInstanceUID": "1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
}
folder = "/tmp/adit_download_folder"
results = connector.c_get(query_dict, folder)
pprint(results)
print()

connector.close_connection()
