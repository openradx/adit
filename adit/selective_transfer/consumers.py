import logging
import re
from datetime import datetime
from operator import itemgetter
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import formats, dateformat
from asgiref.sync import sync_to_async
from adit.main.models import DicomServer
from adit.main.utils.dicom_connector import DicomConnector

logger = logging.getLogger(__name__)


class SelectiveTransferConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        self.user = None
        self.connector = None
        super().__init__(*args, **kwargs)

    async def connect(self):
        logger.debug("Connected to WebSocket client.")
        self.user = self.scope["user"]
        await self.accept()

    async def disconnect(self, close_code):  # pylint: disable=arguments-differ
        logger.debug("Disconnected from WebSocket client with code: %s", close_code)

    async def receive_json(self, msg):  # pylint: disable=arguments-differ
        print(msg)
        await self.send_json({})
