from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from main.utils.dicom_operations import DicomOperation


class QueryStudiesConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):  # pylint: disable=arguments-differ
        print("diconnected")
        print(close_code)

    async def receive_json(self, content):  # pylint: disable=arguments-differ
        print(content)
        await self.send_json(content)
        # if "query" in content:
        # query = content["query"]
        # result = await self.query_studies(query)
        # await self.send_json(result)

    @sync_to_async
    def query_studies(self, query):
        query_dict = {
            "PatientID": query["patient_id"],
            "PatientName": query["patient_name"],
            "PatientBirthDate": query["patient_birth_date"],
            "StudyDate": query["study_date"],
            "Modality": query["modality"],
            "AccessionNumber": query["accession_number"],
        }

        return {"foo": "bar"}
