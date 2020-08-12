from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.conf import settings
from main.models import DicomServer
from main.utils.dicom_handler import DicomHandler


@database_sync_to_async
def fetch_source_server(source_id):
    return DicomServer.objects.get(id=source_id)


@sync_to_async
def query_studies(username: str, server: DicomServer, query: dict):
    config = DicomHandler.Config(
        username=username,
        client_ae_title=settings.ADIT_AE_TITLE,
        source_ae_title=server.ae_title,
        source_ip=server.ip,
        source_port=server.port,
        patient_root_query_model_find=server.patient_root_query_model_find,
        debug=True,
    )

    handler = DicomHandler(config)
    results = handler.find_studies(
        query["patient_id"],
        query["patient_name"],
        query["patient_birth_date"],
        query["accession_number"],
        query["study_date"],
        query["modality"],
    )

    return results


class QueryStudiesConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        self.user = None
        super().__init__(*args, **kwargs)

    async def connect(self):
        self.user = self.scope["user"]
        await self.accept()

    async def disconnect(self, close_code):  # pylint: disable=arguments-differ
        print("diconnected")
        print(close_code)

    async def receive_json(self, query):  # pylint: disable=arguments-differ
        print(query)
        server = await fetch_source_server(query.get("source"))
        result = await query_studies(self.user.username, server, query)
        await self.send_json(result)
