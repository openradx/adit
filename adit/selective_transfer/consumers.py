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


@database_sync_to_async
def _fetch_source_server(source_id):
    if not source_id:
        return None

    try:
        server = DicomServer.objects.get(id=source_id)
    except DicomServer.DoesNotExist:
        server = None
    return server


# TODO Maybe it would be better to use thread_sensitive=True instead
# of threading.lock. Not sure about that or about possible race
# conditions.
# See also https://docs.djangoproject.com/en/3.1/topics/async/#sync-to-async
@sync_to_async
def _query_studies_sync(connector: DicomConnector, query: dict):
    studies = connector.find_studies(
        patient_id=query["patient_id"],
        patient_name=query["patient_name"],
        birth_date=query["patient_birth_date"],
        accession_number=query["accession_number"],
        study_date=query["study_date"],
        modality=query["modality"],
    )
    return sorted(studies, key=itemgetter("StudyDate"), reverse=True)


def _convert_date_from_dicom(date_str):
    dt = datetime.strptime(date_str, "%Y%m%d")
    date_format = formats.get_format("SHORT_DATE_FORMAT")
    return dateformat.format(dt, date_format)


def _convert_date_to_dicom(date_str, field_name):
    dt = None
    date_input_formats = formats.get_format("DATE_INPUT_FORMATS")
    for input_format in date_input_formats:
        try:
            dt = datetime.strptime(date_str, input_format)
            break
        except ValueError:
            pass

    if not dt:
        raise ValueError(f'Invalid date input format of "{field_name}".')

    return dt.strftime("%Y%m%d")


def _convert_name_from_dicom(name_str):
    return name_str.replace("^", ", ")


def _convert_name_to_dicom(name_str):
    return re.sub(r"\s*,\s*", "^", name_str)


def _sanitize_query(query):
    if not query["source"]:
        raise ValueError("Source server missing.")

    if not (
        query["patient_id"]
        or query["patient_name"]
        or query["patient_birth_date"]
        or query["study_date"]
        or query["modality"]
        or query["accession_number"]
    ):
        raise ValueError("You must provide at least one search parameter.")

    if not (
        query["patient_id"]
        or (query["patient_name"] and query["patient_birth_date"])
        or query["accession_number"]
    ):
        raise ValueError(
            'At least "Patient ID" or "Patient Name" / "Birth Date" '
            'or "Accession Nr" must be provided.'
        )

    if query["patient_name"]:
        query["patient_name"] = _convert_name_to_dicom(query["patient_name"])

    if query["study_date"]:
        query["study_date"] = _convert_date_to_dicom(query["study_date"], "Study Date")

    if query["patient_birth_date"]:
        query["patient_birth_date"] = _convert_date_to_dicom(
            query["patient_birth_date"], "Birth Date"
        )


def _convert_query_results(studies):
    for study in studies:
        study["PatientName"] = _convert_name_from_dicom(study["PatientName"])
        study["PatientBirthDate"] = _convert_date_from_dicom(study["PatientBirthDate"])
        study["StudyDate"] = _convert_date_from_dicom(study["StudyDate"])


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
        action = msg.get("action")
        if action == "query_studies":
            self.cancel_query()  # cancel a previous still running query
            await self.query_studies(msg["queryId"], msg["query"])
        elif action == "cancel_query":
            self.cancel_query()

    async def query_studies(self, query_id, query):
        try:
            _sanitize_query(query)

            server = await _fetch_source_server(query.get("source"))
            if not server:
                raise ValueError("Invalid source server.")

            self.connector = server.create_connector()
            studies = await _query_studies_sync(self.connector, query)
            _convert_query_results(studies)
            await self.send_json(
                {"status": "success", "queryId": query_id, "queryResults": studies}
            )
        except ValueError as err:
            await self.send_json({"status": "error", "message": str(err)})

    def cancel_query(self):
        if self.connector and self.connector.is_connected():
            self.connector.c_cancel()
