import asyncio
import logging
from io import BytesIO
from typing import Any
from uuid import UUID

from adit_radis_shared.common.types import AuthenticatedHttpRequest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.generic.edit import FormView
from django_htmx.http import trigger_client_event

from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
from adit.core.views import BaseUpdatePreferencesView

from .forms import UploadForm
from .models import UploadSession

UPLOAD_SOURCE = "upload_source"
UPLOAD_DESTINATION = "upload_destination"

logger = logging.getLogger(__name__)


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


@login_required
async def upload_api_view(request: AuthenticatedHttpRequest, node_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    has_permission = await sync_to_async(lambda: request.user.has_perm("upload.can_upload_data"))()

    if not has_permission:
        raise PermissionDenied()

    file_data = request.FILES

    destination_node = await DicomServer.objects.aget(id=node_id)

    session_id = request.headers.get("X-Upload-Session")
    if session_id is None:
        return HttpResponse(status=400, content="No upload session specified")
    session_id = UUID(session_id)
    session = await UploadSession.objects.aget(id=session_id)

    node_accessible = await sync_to_async(
        lambda: destination_node.is_accessible_by_user(request.user, "destination")
    )()
    if not node_accessible:
        raise PermissionDenied()
    else:
        operator = DicomOperator(destination_node)
        dataset = None
        uploaded_file = None

        if file_data is None:
            return HttpResponse(status=400, content="No data received")

        dataset_size = 0

        if "dataset" in file_data:
            uploaded_file = file_data.get("dataset")
            assert isinstance(uploaded_file, UploadedFile)
            dataset_bytes = BytesIO(uploaded_file.read())
            dataset_size = dataset_bytes.getbuffer().nbytes
            try:
                dataset = read_dataset(dataset_bytes)
            except Exception as e:
                logger.exception(
                    "Failed to read dataset from uploaded file to node %s because of: %s",
                    node_id,
                    e,
                )
                return HttpResponse(status=400, content="Invalid dataset")
            finally:
                dataset_bytes.close()

        if dataset is None or uploaded_file is None:
            return HttpResponse(status=400, content="No data received")
        try:
            session.upload_size += dataset_size
            session.uploaded_file_count += 1
            await sync_to_async(session.save)()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, operator.upload_images, [dataset])

            status = 200
            message = "Upload successful"

        except Exception as e:
            logger.exception("Upload failed to node %s because of: %s", node_id, e)
            status = 500
            message = "Upload failed"

        response = HttpResponse(status=status, content=message)

        response["statusText"] = response.reason_phrase

        return response


@login_required
async def create_upload_session(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = await sync_to_async(UploadSession.objects.create)(owner=request.user)
    return JsonResponse({"session_id": str(data.id), "started_at": data.time_opened})
