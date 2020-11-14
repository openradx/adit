import logging
import asyncio
from time import sleep
from asgiref.sync import async_to_sync
from django.http import QueryDict
from django.template.loader import render_to_string
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from crispy_forms.utils import render_crispy_form
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferJobCreateMixin

QUERY_RESULT_LIMIT = 101

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
        self.current_message_id = 0
        super().__init__(*args, **kwargs)

    async def connect(self):
        logger.debug("Connected to WebSocket client.")
        self.user = self.scope["user"]
        await self.accept()

    async def disconnect(self, close_code):  # pylint: disable=arguments-differ
        if self.connector:
            self.connector.abort_connection()
        logger.debug("Disconnected from WebSocket client with code: %s", close_code)

    async def receive_json(self, content, **kwargs):
        print("recevied message")
        if self.connector:
            self.connector.abort_connection()

        self.current_message_id += 1
        message_id = self.current_message_id

        error_response = await self.check_user()
        if error_response:
            await self.send_json(error_response)
            return

        form = SelectiveTransferJobForm(QueryDict(content["data"]))
        form_valid = await database_sync_to_async(form.is_valid)()

        if content["action"] == "query":
            if form_valid:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, self.make_query, form, message_id)
            else:
                response = self.get_form_error_response(
                    form, "Please correct the form errors and search again."
                )
                await self.send_json(response)

        elif content["action"] == "transfer":
            if form_valid:
                asyncio.create_task(self.make_transfer(form))
            else:
                response = self.get_form_error_response(
                    form, "Please correct the form errors and transfer again."
                )
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
    def get_form_error_response(self, form, message):
        return {
            "#query_form": render_crispy_form(form),
            "#error_message": render_error_message(message),
        }

    def make_query(self, form, message_id):
        print("query start")
        if message_id != self.current_message_id:
            return
        self.connector = self.create_source_connector(form)
        if message_id != self.current_message_id:
            return

        try:
            print("before query")
            studies = self.query_studies(self.connector, form, QUERY_RESULT_LIMIT)
            if message_id != self.current_message_id:
                return
            print(studies)
            print("after query")
            response = self.get_query_response(form, studies)
            if message_id != self.current_message_id:
                return
            async_to_sync(self.send_json)(response)
        except ConnectionError:
            # Ignore connection aborts (most probably from ourself)
            # Maybe we should check here if we really aborted the connection
            pass

    async def make_transfer(self, form):
        selected_studies = form.data.getlist("selected_studies")
        response = await self.get_transfer_response(form, selected_studies)
        await self.send_json(response)

    def get_query_response(self, form, studies):
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
