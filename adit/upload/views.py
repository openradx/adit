import asyncio
import io
import sqlite3 as sql
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

import pydicom
from asgiref.sync import sync_to_async
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from pydicom import Dataset
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response

from adit.core.decorators import login_required_async, permission_required_async
from adit.core.models import DicomNode, DicomServer
from adit.core.types import AuthenticatedRequest
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.views import (
    BaseUpdatePreferencesView,
    DicomJobCreateView,
)
from adit.dicom_web.views import StoreAPIView

from .forms import UploadJobForm

UPLOAD_SOURCE = "upload_source"
UPLOAD_DESTINATION = "upload_destination"


class UploadUpdatePreferencesView(BaseUpdatePreferencesView):
    allowed_keys: list[str] = [
        UPLOAD_SOURCE,
        UPLOAD_DESTINATION,
    ]


class UploadJobCreateView(DicomJobCreateView):
    template_name = "upload/upload_job_form.html"
    form_class = UploadJobForm
    permission_required = "upload.add_uploadjob"
    # model = UploadJob

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()

        kwargs["action"] = self.request.POST.get("action")
        kwargs["user"] = self.request.user

        return kwargs

    def get_initial(self):
        initial = super().get_initial()

        preferences: dict[str, Any] = self.request.user.preferences

        source = preferences.get(UPLOAD_SOURCE)
        if source is not None:
            initial["source"] = source

        destination = preferences.get(UPLOAD_DESTINATION)
        if destination is not None:
            initial["destination"] = destination

        return initial


# @login_required_async
# @sync_to_async
async def uploadAPIView(request, node_id: str) -> HttpResponse:
    status = 0
    message = ""
    pool = ThreadPoolExecutor()
    if request.method == "POST":
        data = request.FILES
        dataset = None

        if "dataset" in data:
            dataset_bytes = data["dataset"].read()
            dataset_bytes = BytesIO(dataset_bytes)
            dataset = pydicom.dcmread(dataset_bytes, force=True)

            if "node_id" in data:
                selected_id = int(node_id)
                destination_node = await sync_to_async(
                    lambda: DicomServer.objects.get(id=selected_id)
                )()

                operator = DicomOperator(destination_node)

                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, operator.upload_instances, [dataset])
                    status = 200

                    message = "Upload erfolgreich"
                except:
                    status = 500
                    message = "Upload fehlgeschlagen"

            else:
                status = 400
                message = "keine NodeID erhalten "

        else:
            status = 400
            message = "keine Daten enthalten"

    response = HttpResponse(status=status, content=message)

    response["statusText"] = response.reason_phrase

    return response
