import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from adit.main.models import DicomServer

logger = logging.getLogger("adit." + __name__)


@database_sync_to_async
def fetch_source_server(source_id):
    if not source_id:
        return None

    try:
        server = DicomServer.objects.get(id=source_id)
    except DicomServer.DoesNotExist:
        server = None
    return server


@sync_to_async
def query_studies(server: DicomServer, query: dict):
    connector = server.create_connector()
    results = connector.find_studies(
        query["patient_id"],
        query["patient_name"],
        query["patient_birth_date"],
        query["accession_number"],
        query["study_date"],
        query["modality"],
    )
    return results


class SelectiveTransferConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        self.user = None
        super().__init__(*args, **kwargs)

    async def connect(self):
        logger.debug("Connected to WebSocket client.")
        self.user = self.scope["user"]
        await self.accept()

    async def disconnect(self, close_code):  # pylint: disable=arguments-differ
        logger.debug("Disconnected from WebSocket client with code: %s", close_code)

    async def receive_json(self, msg):  # pylint: disable=arguments-differ
        if msg.get("action") == "query_studies":
            query_id = msg["queryId"]
            query = msg["query"]

            if not query.get("source"):
                await self.send_json(
                    {"status": "ERROR", "message": "Source server missing."}
                )

            server = await fetch_source_server(query.get("source"))
            if not server:
                self.send_json({"status": "ERROR", "message": "Invalid source server."})
            else:
                results = await query_studies(server, query)
                await self.send_json(
                    {"status": "SUCCESS", "queryId": query_id, "queryResults": results}
                )

    def cancel_query(self):
        raise NotImplementedError()
        # self.assoc.accepted_contexts[0].context_id
