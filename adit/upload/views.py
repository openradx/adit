from typing import Any

from adit.core.models import DicomServer
from adit.core.types import AuthenticatedRequest
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


class UploadAPIView(StoreAPIView):
    async def post(self, request: AuthenticatedRequest, ae_title: str = "", study_uid: str = ""):
        # Set the ae_title value here
        servers = DicomServer.objects.all()
        ae_title = servers[int(request.user.preferences[UPLOAD_DESTINATION])].ae_title
        print(ae_title)
        # Call the super().post() method with the updated parameters
        return super().post(request, ae_title, study_uid)
