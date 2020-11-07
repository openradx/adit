import os
from os import environ
from pathlib import Path
import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Clear both Orthanc instances and upload DICOM files to Orthanc 1 instance."

    def handle(self, *args, **options):
        print("Resetting Orthancs.")

        dicoms_folder = settings.BASE_DIR / "samples" / "dicoms"

        orthanc1_host = environ.get("ORTHANC1_HOST", "localhost")
        handler = OrthancRestHandler(host=orthanc1_host, port=6501)
        handler.clear()

        handler.upload_files(dicoms_folder)

        orthanc2_host = environ.get("ORTHANC2_HOST", "localhost")
        handler = OrthancRestHandler(host=orthanc2_host, port=6502)
        handler.clear()


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

    def upload_files(self, folder_to_upload):
        for root, _, files in os.walk(folder_to_upload):
            for file in files:
                dicom_file_path = Path(root) / file
                with open(dicom_file_path, "rb") as f:
                    payload = f.read()
                    r = self.session.post(
                        f"http://{self.host}:{self.port}/instances", data=payload
                    )
                    r.raise_for_status()

    def list(self, resource_type=PATIENTS_RESOURCE):
        r = self.session.get(f"http://{self.host}:{self.port}/{resource_type}")
        r.raise_for_status()
        return r.json()

    def delete(self, res_ids, resource_type=PATIENTS_RESOURCE):
        for res_id in res_ids:
            r = self.session.delete(
                f"http://{self.host}:{self.port}/{resource_type}/{res_id}"
            )
            r.raise_for_status()

    def clear(self):
        res_ids = self.list()
        self.delete(res_ids)

    def find(self, query=None):
        if query is None:
            query = {}
        r = self.session.post(f"http://{self.host}:{self.port}/tools/find", json=query)
        r.raise_for_status()
        return r.json()


# Demo of OrthancRestHandler:
# parent_dir = os.path.dirname(os.path.realpath(__file__))
# dicom_dir = os.path.join(parent_dir, 'samples', 'dicoms')
# handler = OrthancRestHandler(port=6501)
# handler.upload_files(dicom_dir)
# r = handler.find({
#     'Level' : OrthancRestHandler.STUDIES_RESOURCE,
#     'Query' : {
#         'Modality' : 'MR'
#     },
#     'Expand': True
# })
# handler.clear_orthanc()