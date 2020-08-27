import sys
from pathlib import Path
from pprint import pprint

path = Path(__file__).parent.parent.resolve()
sys.path.append(path.as_posix())

# pylint: disable-msg=wrong-import-position
from main.utils.dicom_connector import DicomConnector

config = DicomConnector.Config("ADIT", "ORTHANC1", "127.0.0.1", 7501)
connector = DicomConnector(config)

connector.open_connection()

query_dict = {
    "QueryRetrieveLevel": "PATIENT",
    "PatientName": "Banana^Ben",
    "PatientBirthDate": "19620218",
    "PatientID": "",
}
results = connector.c_find(query_dict)
pprint(results)
print("---")

patient_id = None
for patient in map(lambda x: x["data"], results):
    if (
        "PatientBirthDate" in patient
        and patient["PatientBirthDate"] == query_dict["PatientBirthDate"]
    ):
        if patient_id is not None:
            print("Warning: More than one patient id.")
        patient_id = patient["PatientID"]
pprint(patient_id)
print("---")

query_dict["QueryRetrieveLevel"] = "STUDY"
query_dict["PatientID"] = patient_id
query_dict["StudyInstanceUID"] = ""
query_dict["StudyDescription"] = ""
results = connector.c_find(query_dict)
pprint(results)
print("---")

query_dict["QueryRetrieveLevel"] = "SERIES"
query_dict["StudyInstanceUID"] = results[0]["data"]["StudyInstanceUID"]
query_dict["SeriesInstanceUID"] = ""
query_dict["Modality"] = ""
results = connector.c_find(query_dict)
pprint(results)

connector.close_connection()
