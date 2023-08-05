import asyncio
import contextlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from crispy_forms.utils import render_crispy_form
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string

from adit.accounts.models import User
from adit.core.utils.dicom_connector import DicomConnector

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


def render_query_hint():
    return render_to_string("selective_transfer/_query_hint.html")


def render_query_in_progress():
    return render_to_string("selective_transfer/_query_in_progress.html")


def render_error_message(message):
    return render_to_string(
        "selective_transfer/_error_message.html",
        {"error_message": str(message)},
    )


class SelectiveTransferConsumer(SelectiveTransferJobCreateMixin, AsyncJsonWebsocketConsumer):
    async def connect(self):
        logger.debug("Connected to WebSocket client.")

        self.user: User = self.scope["user"]
        self.session: SessionStore = self.scope["session"]
        self.query_connectors: list[DicomConnector] = []
        self.current_message_id: int = 0
        self.pool = ThreadPoolExecutor()

        await self.accept()

    async def disconnect(self, code):
        self.abort_connectors()
        self.pool.shutdown(wait=False, cancel_futures=True)
        logger.debug("Disconnected from WebSocket client with code: %s", code)

    async def receive_json(self, content, **kwargs):
        error_response = await self.check_permission()
        if error_response:
            await self.send(error_response)
            return

        action = content.get("action")
        if action not in ["query", "cancel", "reset", "transfer"]:
            await self.send(render_error_message(f"Invalid action to process: {action}"))

        async with async_lock(lock):
            self.current_message_id += 1
            message_id = self.current_message_id
            self.abort_connectors()

        if action == "cancel" or action == "reset":
            # We always abort the connection when a new request is received, so
            # we don't have to do anything special here.
            await self.send(render_query_hint())
            return

        form = SelectiveTransferJobForm(content, user=self.user, action=action)
        form_valid: bool = await database_sync_to_async(form.is_valid)()

        if form_valid:
            self.save_initial_form_data(self.session, form)
            # Sessions must be explicitly saved in an Channels consumer
            # https://channels.readthedocs.io/en/stable/topics/sessions.html#session-persistence
            await sync_to_async(self.session.save)()

        if action == "query":
            if form_valid:
                await self.send(render_query_in_progress())
                asyncio.create_task(self.make_query(form, message_id))
            else:
                form_error_response = await self.build_form_error_response(
                    form, "Please correct the form errors and search again."
                )
                await self.send(form_error_response)

        elif action == "transfer":
            if form_valid:
                asyncio.create_task(self.make_transfer(form))
            else:
                form_error_response = await self.build_form_error_response(
                    form, "Please correct the form errors and transfer again."
                )
                await self.send(form_error_response)

        else:
            raise ValueError(f"Invalid action to process: {action}")

    def abort_connectors(self):
        while self.query_connectors:
            for connector in self.query_connectors[:]:
                self.query_connectors.remove(connector)
                connector.abort_connection()

    @database_sync_to_async
    def check_permission(self):
        if not self.user:
            return render_error_message("Access denied. You must be logged in.")

        if not self.user.has_perm("selective_transfer.add_selectivetransferjob"):
            return render_error_message("Access denied. You don't have the proper permission.")

        return None

    @database_sync_to_async
    def build_form_error_response(self, form, message):
        rendered_form = render_crispy_form(form)
        rendered_error_message = render_error_message(message)
        return rendered_form + rendered_error_message

    async def make_query(self, form, message_id):
        loop = asyncio.get_event_loop()
        query_response = await loop.run_in_executor(
            self.pool, self.build_query_response, form, message_id
        )
        await self.send(query_response)

    def build_query_response(self, form, message_id):
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
                # Rerender form to remove potential previous error messages
                rendered_form = render_crispy_form(form)
                rendered_query_results = render_to_string(
                    "selective_transfer/_query_results.html",
                    {
                        "query": True,
                        "query_results": studies,
                        "max_query_results": max_query_results,
                        "exclude_modalities": settings.EXCLUDED_MODALITIES,
                    },
                )
                return rendered_form + rendered_query_results

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
        selected_studies = form.data.get("selected_studies")
        if selected_studies and isinstance(selected_studies, str):
            selected_studies = [selected_studies]
        response = await self.build_transfer_response(form, selected_studies)
        await self.send(response)

    @database_sync_to_async
    def build_transfer_response(self, form, selected_studies):
        rendered_form = render_crispy_form(form)

        try:
            job = self.transfer_selected_studies(self.user, form, selected_studies)
        except ValueError as err:
            rendered_error_message = render_error_message(str(err))
            return rendered_form + rendered_error_message

        rendered_created_job = render_to_string(
            "selective_transfer/_created_job.html",
            {"transfer": True, "created_job": job},
        )
        return rendered_form + rendered_created_job
