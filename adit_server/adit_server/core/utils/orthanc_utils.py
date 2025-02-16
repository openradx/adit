from pathlib import Path

import requests


class OrthancRestHandler:
    PATIENTS_RESOURCE = "patients"
    STUDIES_RESOURCE = "studies"
    SERIES_RESOURCE = "series"
    INSTANCES_RESOURCE = "instances"

    def __init__(self, host="localhost", port=8042):
        self.host = host
        self.port = port

        # Force requests to not use any set proxy (by http_proxy env variable).
        # Orthancs for testing are always in the same local network.
        self.session = requests.Session()
        self.session.trust_env = False

    def upload(self, folder_to_upload):
        for path in Path(folder_to_upload).rglob("*"):
            if not path.is_file():
                continue

            with open(path, "rb") as f:
                payload = f.read()
                r = self.session.post(f"http://{self.host}:{self.port}/instances", data=payload)
                r.raise_for_status()

    def list(self, resource_type=STUDIES_RESOURCE):
        r = self.session.get(f"http://{self.host}:{self.port}/{resource_type}")
        r.raise_for_status()
        return r.json()

    def delete(self, res_ids, resource_type=STUDIES_RESOURCE):
        for res_id in res_ids:
            r = self.session.delete(f"http://{self.host}:{self.port}/{resource_type}/{res_id}")
            r.raise_for_status()

    def clear(self, full_clear=False):
        res_ids = self.list(resource_type=self.PATIENTS_RESOURCE)
        self.delete(res_ids, resource_type=self.PATIENTS_RESOURCE)

        if full_clear:
            r = self.session.delete(f"http://{self.host}:{self.port}/changes")
            r.raise_for_status()
            r = self.session.delete(f"http://{self.host}:{self.port}/exports")
            r.raise_for_status()

    def find(self, query):
        r = self.session.post(f"http://{self.host}:{self.port}/tools/find", json=query)
        r.raise_for_status()
        return r.json()


# Demo of OrthancRestHandler:
# parent_folder = os.path.dirname(os.path.realpath(__file__))
# dicom_folder = Path(parent_folder) / "samples" / "dicoms"
# handler = OrthancRestHandler(port=6501)
# handler.upload(dicom_folder)
# r = handler.find({
#     'Level' : OrthancRestHandler.STUDIES_RESOURCE,
#     'Query' : {
#         'Modality' : 'MR'
#     },
#     'Expand': True
# })
# handler.clear_orthanc()
