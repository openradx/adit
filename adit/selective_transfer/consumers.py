import logging
from django.http import QueryDict
from django.template.loader import render_to_string
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from crispy_forms.utils import render_crispy_form
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferJobCreateMixin

QUERY_RESULT_LIMIT = 51

logger = logging.getLogger(__name__)


def render_error_message(error_message):
    return (
        render_to_string(
            "selective_transfer/_error_message.html",
            {"error_message": str(error_message)},
        ),
    )


def create_error_response(error_message):
    return {
        "#error_message": render_error_message(error_message),
        "#query_results": "",
        "#created_job": "",
    }


class SelectiveTransferConsumer(
    SelectiveTransferJobCreateMixin, AsyncJsonWebsocketConsumer
):
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

    async def receive_json(self, content, **kwargs):
        error_response = await self.check_user()
        if error_response:
            error_response["messageId"] = content["messageId"]
            await self.send_json(error_response)
            return

        form_data = QueryDict(content["data"])

        if content["action"] == "query":
            await self.make_query(form_data, content["messageId"])

        elif content["action"] == "transfer":
            await self.make_transfer(form_data, content["messageId"])

    @database_sync_to_async
    def check_user(self):
        if not self.user:
            return create_error_response("Access denied. You must be logged in.")

        if not self.user.has_perm("selective_transfer.add_selectivetransferjob"):
            return create_error_response(
                "Access denied. You don't have the proper permission."
            )

        return None

    async def make_query(self, form_data, message_id):
        form = SelectiveTransferJobForm(form_data)
        response = await self.get_query_response(form)
        response["messageId"] = message_id
        await self.send_json(response)

    async def make_transfer(self, form_data, message_id):
        form = SelectiveTransferJobForm(form_data)
        selected_studies = form_data.getlist("selected_studies")
        response = await self.get_transfer_response(form, selected_studies)
        response["messageId"] = message_id
        await self.send_json(response)

    @database_sync_to_async
    def get_query_response(self, form):
        if not form.is_valid():
            return {
                "#query_form": render_crispy_form(form),
                "#error_message": render_error_message(
                    "Please correct the form errors and search again."
                ),
            }

        studies = self.query_studies(form, QUERY_RESULT_LIMIT)

        max_query_results = len(studies) >= QUERY_RESULT_LIMIT

        return {
            "#query_form": render_crispy_form(form),
            "#query_results": render_to_string(
                "selective_transfer/_query_results.html",
                {
                    "query": True,
                    "query_results": studies,
                    "max_query_results": max_query_results,
                },
            ),
            "#error_message": "",
            "#created_job": "",
        }

    @database_sync_to_async
    def get_transfer_response(self, form, selected_studies):
        if not form.is_valid():
            return {
                "#query_form": render_crispy_form(form),
                "#error_message": render_error_message(
                    "Please correct the form errors and transfer again."
                ),
            }

        try:
            job = self.transfer_selected_studies(self.user, form, selected_studies)
        except ValueError as err:
            return {
                "#query_form": render_crispy_form(form),
                "#error_message": render_error_message(str(err)),
            }

        return {
            "#query_form": render_crispy_form(form),
            "#created_job": render_to_string(
                "selective_transfer/_created_job.html",
                {"transfer": True, "created_job": job},
            ),
            "#error_message": "",
            "#query_results": "",
        }
