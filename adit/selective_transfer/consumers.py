import logging
import contextlib
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from django.http import QueryDict
from django.conf import settings
from django.template.loader import render_to_string
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from crispy_forms.utils import render_crispy_form
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferJobCreateMixin

logger = logging.getLogger(__name__)

lock = threading.Lock()


@contextlib.asynccontextmanager
async def async_lock(_lock):
    """To handle a thread lock in async code.

    See https://stackoverflow.com/a/63425191/166229
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _lock.acquire)
    try:
        yield  # the lock is held
    finally:
        _lock.release()


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
    async def connect(self):
        logger.debug("Connected to WebSocket client.")

        self.user = self.scope["user"]
        self.query_connectors = []
        self.current_message_id = 0
        self.pool = ThreadPoolExecutor()

        await self.accept()

    async def disconnect(self, code):
        self.abort_connectors()
        self.pool.shutdown(wait=False, cancel_futures=True)
        logger.debug("Disconnected from WebSocket client with code: %s", code)

    async def receive_json(self, content, **kwargs):
        async with async_lock(lock):
            self.current_message_id += 1
            message_id = self.current_message_id
            self.abort_connectors()

        if content["action"] == "cancelQuery":
            return

        error_response = await self.check_permission()
        if error_response:
            await self.send_json(error_response)
            return

        query_form = content["action"] == "query"

        form = SelectiveTransferJobForm(
            QueryDict(content["data"]),
            user=self.user,
            query_form=query_form,
        )
        form_valid = await database_sync_to_async(form.is_valid)()

        if content["action"] == "query":
            if form_valid:
                asyncio.create_task(self.make_query(form, message_id))
            else:
                response = await self.get_form_error_response(
                    form, "Please correct the form errors and search again."
                )
                await self.send_json(response)

        elif content["action"] == "transfer":
            if form_valid:
                asyncio.create_task(self.make_transfer(form))
            else:
                response = await self.get_form_error_response(
                    form, "Please correct the form errors and transfer again."
                )
                await self.send_json(response)

    def abort_connectors(self):
        while self.query_connectors:
            for connector in self.query_connectors[:]:
                self.query_connectors.remove(connector)
                connector.abort_connection()

    @database_sync_to_async
    def check_permission(self):
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

    async def make_query(self, form, message_id):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            self.pool, self.get_query_response, form, message_id
        )
        if response:
            await self.send_json(response)

    def get_query_response(self, form, message_id):
        with lock:
            if message_id != self.current_message_id:
                return None
            connector = self.create_source_connector(form)
            self.query_connectors.append(connector)

        try:
            limit = settings.SELECTIVE_TRANSFER_RESULT_LIMIT
            studies = self.query_studies(connector, form, limit)
            max_query_results = len(studies) >= limit
            if message_id == self.current_message_id:
                return {
                    "#query_form": render_crispy_form(form),
                    "#query_results": render_to_string(
                        "selective_transfer/_query_results.html",
                        {
                            "query": True,
                            "query_results": studies,
                            "max_query_results": max_query_results,
                            "exclude_modalities": settings.EXCLUDE_MODALITIES,
                        },
                    ),
                    "#error_message": "",
                    "#created_job": "",
                }
        except ConnectionError:
            # Ignore connection aborts (most probably from ourself)
            # Maybe we should check here if we really aborted the connection
            pass
        finally:
            with lock:
                if connector in self.query_connectors:
                    self.query_connectors.remove(connector)

        return None

    async def make_transfer(self, form):
        selected_studies = form.data.getlist("selected_studies")
        response = await self.get_transfer_response(form, selected_studies)
        await self.send_json(response)

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
