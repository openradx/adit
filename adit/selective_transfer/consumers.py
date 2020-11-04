import logging
from django.http import QueryDict
from django.template.loader import render_to_string
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from crispy_forms.utils import render_crispy_form
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferJobCreateMixin

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

        data = QueryDict(content["data"])
        form = SelectiveTransferJobForm(data)

        if content["action"] == "query":
            response = await self.get_query_response(form)
            response["messageId"] = content["messageId"]
            await self.send_json(response)

        elif content["action"] == "transfer":
            selected_studies = data.getlist("selected_studies")
            response = await self.get_transfer_response(form, selected_studies)
            response["messageId"] = content["messageId"]
            await self.send_json(response)

    @database_sync_to_async
    def check_user(self):
        if not self.user:
            return create_error_response("Access denied. You must be logged in.")

        if not self.user.has_perm("selective_transfer.add_selectivetransferjob"):
            return create_error_response(
                "Access denied. You don't have the proper permission."
            )

        return None

    @database_sync_to_async
    def get_query_response(self, form):
        if not form.is_valid():
            return {
                "#query_form": render_crispy_form(form),
                "#error_message": render_error_message(
                    "Please correct the form errors and search again."
                ),
            }

        studies = self.do_query(form)
        return {
            "#query_form": render_crispy_form(form),
            "#query_results": render_to_string(
                "selective_transfer/_query_results.html",
                {"query": True, "query_results": studies},
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
            job = self.do_transfer(self.user, form, selected_studies)
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
