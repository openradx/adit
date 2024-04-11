import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from os import error
from typing import Any

# import bs4
import pydicom
from asgiref.sync import sync_to_async
from crispy_forms.utils import render_crispy_form
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.forms import Form
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.context_processors import csrf
from django_htmx.http import trigger_client_event
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response

from adit.core.decorators import login_required_async, permission_required_async
from adit.core.models import DicomNode, DicomServer
from adit.core.types import AuthenticatedHttpRequest
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
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
    request: AuthenticatedHttpRequest
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

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs):
        import sys

        print(sys.path)
        if not request.htmx:
            raise SuspiciousOperation("Only accessible by HTMX")
        print(
            "\n\n\nrequest:",
            request.POST,
            "\n::\n",
        )
        form = UploadJobForm(
            request.POST,
            user=request.user,
            action="transfer",
        )

        if form.is_valid():
            success = {"Correct entrys"}
            context = {"form": form, "success": success}

            print("valid")
            response = HttpResponse(status=204)  # 204 = Success without response (kein body)
            response = trigger_client_event(response, "chooseFolder")
            print(response)
            return response

        else:
            # print(f"not valid, {form.errors},", "\n::\n", form.error_class, "\n::\n", form.data)
            # print(form.media)
            # rendered_form = render(
            #     request,
            #     "upload/upload_job_form_partial.html",
            #     {
            #         "div_id_pseudonym": form.fields.get("pseudonym"),
            #         "div_id_destination": form.fields.get("destination"),
            #     },
            # )
            # print(rendered_form, "\n::\n")
            print(form.helper.layout, "\n::\n")
            print(form, "\n::\n")
            print(form["pseudonym"], "\n::\n")
            print(form["destination"], "\n::\n")
            print(form.base_fields, "\n::\n")
            ctx = {}
            ctx.update(csrf(request))
            x = render_crispy_form(form, context=ctx)
            print(x, "\n::\n")
            print(type(x), "\n::\n")
            # soup = BeautifulSoup(x, "html.parser")
            # inner_part = soup.find("div", id="form_partial")

            # print(inner_part, "\n::\n")
            print("-" * 30, "END OF RESPONSE", "-" * 30)
            return render(
                request,
                "upload/upload_job_form_partial.html",
                {
                    "div_id_pseudonym": form.fields.get("pseudonym"),
                    "div_id_destination": form.fields.get("destination"),
                },
            )


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
    print(status)
    response = HttpResponse(status=status, content=message)

    response["statusText"] = response.reason_phrase

    return response
