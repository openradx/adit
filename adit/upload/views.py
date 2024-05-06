import asyncio
from io import BytesIO
from os import error
from typing import Any

from asgiref.sync import sync_to_async
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponse
from django.shortcuts import render
from django_htmx.http import trigger_client_event

from adit.core.decorators import login_required_async, permission_required_async
from adit.core.models import DicomServer
from adit.core.types import AuthenticatedHttpRequest
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
from adit.core.views import (
    BaseUpdatePreferencesView,
    DicomJobCreateView,
)

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
    request: AuthenticatedHttpRequest

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

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs):

        if not request.htmx:
            raise SuspiciousOperation("Only accessible by HTMX")


        form = UploadJobForm(
            request.POST,
            user=request.user,
            action="transfer",
        )

        if form.is_valid():
            return trigger_client_event(
                render(request, "upload/upload_job_form_swappable.html", {"form": form}),
                "chooseFolder",
            )

        else:
            return render(request, "upload/upload_job_form_swappable.html", {"form": form})


@login_required_async
async def uploadAPIView(request: AuthenticatedHttpRequest, node_id: str) -> HttpResponse:
    status = 0
    message = ""

    if request.method == "POST":
        data = request.FILES

        if "dataset" in data:
            dataset_bytes = data["dataset"].read()
            dataset_bytes = BytesIO(dataset_bytes)
            dataset = read_dataset(dataset_bytes)

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

                except error:
                    print(error)
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
