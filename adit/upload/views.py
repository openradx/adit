import asyncio
from io import BytesIO
from typing import Any

from adit_radis_shared.common.decorators import login_required_async
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic.edit import FormView
from django_htmx.http import trigger_client_event

from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
from adit.core.views import BaseUpdatePreferencesView

from .forms import UploadForm

UPLOAD_SOURCE = "upload_source"
UPLOAD_DESTINATION = "upload_destination"


class UploadUpdatePreferencesView(BaseUpdatePreferencesView):
    allowed_keys: list[str] = [
        UPLOAD_SOURCE,
        UPLOAD_DESTINATION,
    ]


class UploadCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FormView,
):
    template_name = "upload/upload_job_form.html"
    form_class = UploadForm
    permission_required = "upload.can_upload_data"
    request: AuthenticatedHttpRequest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["anon_seed"] = settings.ANONYMIZATION_SEED
        return context

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["action"] = self.request.POST.get("action")
        kwargs["user"] = self.request.user

        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        preferences: dict[str, Any] = self.request.user.preferences
        source = preferences.get(UPLOAD_SOURCE)
        destination = preferences.get(UPLOAD_DESTINATION)

        if source is not None:
            initial["source"] = source

        if destination is not None:
            initial["destination"] = destination

        return initial

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs):
        if not request.htmx:
            raise SuspiciousOperation("Only accessible by HTMX")

        form = UploadForm(
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
async def upload_api_view(request: AuthenticatedHttpRequest, node_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    has_permission = await sync_to_async(lambda: request.user.has_perm("upload.can_upload_data"))()

    if not has_permission:
        raise PermissionDenied()

    file_data = request.FILES

    destination_node = await DicomServer.objects.aget(id=node_id)

    node_accessible = await sync_to_async(
        lambda: destination_node.is_accessible_by_user(request.user, "destination")
    )()
    if not node_accessible:
        raise PermissionDenied()
    else:
        operator = DicomOperator(destination_node)

        if "dataset" in file_data:
            uploaded_file = file_data["dataset"]
            assert isinstance(uploaded_file, UploadedFile)
            dataset_bytes = BytesIO(uploaded_file.read())
            dataset = read_dataset(dataset_bytes)

        if dataset is None or uploaded_file is None:
            return HttpResponse(status=400, content="No data received")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, operator.upload_instances, [dataset])

            status = 200
            message = "Upload successful"

        except Exception:
            status = 500
            message = "Upload failed"

        response = HttpResponse(status=status, content=message)

        response["statusText"] = response.reason_phrase

        return response
