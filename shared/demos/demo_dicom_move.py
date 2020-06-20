import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from ..dicom_operations import Config, DicomMove # pylint: disable-msg=import-error

config = Config(
    "W999999",
    "192.168.0.1",
    104,
    "Synapse"
)
move = DicomMove(config)

query_dict = {
    "QueryRetrieveLevel": "SERIES",
    "PatientID": "8422555",
    "StudyInstanceUID": "xxx",
    "SeriesInstanceUID": "xxx" # CT Topo
}
response = move.send_c_move(query_dict, "DEST_AE_TITLE")
print(response)