import requests
import os

class OrthancRestHandler:
    PATIENTS_RESOURCE = 'patients'
    STUDIES_RESOURCE = 'studies'
    SERIES_RESOURCE = 'series'
    INSTANCES_RESOURCE = 'instances'

    def __init__(self, host='localhost', port=8042):
        self.host = host
        self.port = port

    def upload_files(self, folder_to_upload):
        for root, dirs, files in os.walk(folder_to_upload):
            for file in files:
                dicom_file = os.path.join(root, file)
                with open(dicom_file, 'rb') as f:
                    payload = f.read()
                    r = requests.post(f'http://{self.host}:{self.port}/instances', data=payload)
                    r.raise_for_status()

    def list(self, resource_type=PATIENTS_RESOURCE):
        r = requests.get(f'http://{self.host}:{self.port}/{resource_type}')
        r.raise_for_status()
        return r.json()

    def delete(self, res_ids, resource_type=PATIENTS_RESOURCE):
        for res_id in res_ids:
            r = requests.delete(f'http://{self.host}:{self.port}/{resource_type}/{res_id}')
            r.raise_for_status()

    def clear(self):
        res_ids = self.list()
        self.delete(res_ids)

    def find(self, query={}):
        r = requests.post(f'http://{self.host}:{self.port}/tools/find', json=query)
        r.raise_for_status()
        return r.json()
        
# Demo: 
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

