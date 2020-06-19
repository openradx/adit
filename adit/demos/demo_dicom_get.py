import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from dicom_operations import Config, DicomGet # pylint: disable-msg=import-error

config = Config(
    "W123232",
    "192.168.0.1",
    104,
    "SynapseV4",
    patient_root_query_model=False # Synapse PACS server only supports study root query model for C-GET operations
)
get = DicomGet(config)

query_dict = {
    "QueryRetrieveLevel": "STUDY",
    "PatientID": "xxx",
    "StudyInstanceUID": "xxx"
}
results = get.send_c_get(query_dict, "V:\\ext02\\THOR-SchlampKai\\DICOM")
print(results)