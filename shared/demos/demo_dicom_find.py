import sys, os
from pprint import pprint
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from ..dicom_operations import Config, DicomFind # pylint: disable-msg=import-error

config = Config(
    "W123232",
    "192.168.0.1",
    104,
    "SynapseV4"
)
find = DicomFind(config)


query_dict = {
    "QueryRetrieveLevel": "PATIENT",
    "PatientName": "xxxx, xxx",
    "PatientBirthDate": "19990101",
    "PatientID": ""
}
results = find.send_c_find(query_dict)
pprint(results)
print("---")

patient_id = None
for patient in map(lambda x: x['data'], results):
    if ("PatientBirthDate" in patient and 
            patient["PatientBirthDate"] == query_dict["PatientBirthDate"]):
        if patient_id is not None:
            print('Warning: More than one patient id.')
        patient_id = patient["PatientID"]
pprint(patient_id)
print("---")

query_dict["QueryRetrieveLevel"] = "STUDY"
query_dict["PatientID"] = patient_id
query_dict["StudyInstanceUID"] = ""
query_dict["StudyDescription"] = ""
results = find.send_c_find(query_dict)
pprint(results)
print("---")

query_dict["QueryRetrieveLevel"] = "SERIES"
query_dict["StudyInstanceUID"] = results[1]["data"]["StudyInstanceUID"]
query_dict["SeriesInstanceUID"] = ""
query_dict["Modality"] = ""
results = find.send_c_find(query_dict)
pprint(results)