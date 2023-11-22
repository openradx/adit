import asyncio
from typing import Any, Literal

from adrf.views import APIView as AsyncApiView
from adrf.views import sync_to_async
from django.conf import settings
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from rest_framework.exceptions import NotAcceptable, NotFound, ParseError, ValidationError
from rest_framework.response import Response

from adit.core.models import DicomServer
from adit.core.types import AuthenticatedRequest
from adit.core.views import (
    BaseUpdatePreferencesView,
    DicomJobCancelView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomJobVerifyView,
    DicomTaskDetailView,
    TransferJobListView,
)
from adit.dicom_web.views import WebDicomAPIView

from .forms import UploadJobForm
from .mixins import UploadLockedMixin
from adit.dicom_web.utils.stowrs_utils import stow_store

UPLOAD_SOURCE = "upload_source"
UPLOAD_DESTINATION = "upload_destination"


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


class UploadDataView(WebDicomAPIView):
    async def handle_request(self, request: AuthenticatedRequest, ae_title: str) -> DicomServer:
        return await self._fetch_dicom_server(request, ae_title, "destination")

    async def post(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
        study_uid: str = "",
    ) -> Response:
        dest_server = await self.handle_request(request, ae_title)

        if study_uid:
            datasets = [
                dataset
                for dataset in request.data["datasets"]
                if dataset.StudyInstanceUID == study_uid
            ]
        else:
            datasets = request.data["datasets"]

        results = await stow_store(dest_server, datasets)

        return Response(results, content_type=request.accepted_renderer.media_type)  # type: ignore
