import asyncio
from asgiref.sync import sync_to_async
from django.views.generic.edit import FormView
from django.core.exceptions import SuspiciousOperation
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import DicomExplorerQueryForm


@sync_to_async
@login_required
def check_permission(request):
    # A dummy function for the permission decorators
    pass


@sync_to_async
def get_form(request):
    if not request.GET.get("query"):
        form = DicomExplorerQueryForm()
    else:
        form = DicomExplorerQueryForm(request.GET)
    return form


@sync_to_async
def create_form_response(request, form):
    return render(request, "dicom_explorer/dicom_explorer_form.html", {"form": form})


async def create_result_response(request, form):
    server = form.cleaned_data["server"]
    connector = server.create_connector()
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, query_server)
    return await query_result(request)


@sync_to_async
def query_server(request):
    return render(request, "dicom_explorer/dicom_explorer_result.html", {})


async def dicom_explorer_view(request):
    denied_response = await check_permission(request)
    if denied_response:
        return denied_response

    form = await get_form(request)
    form_valid = await sync_to_async(form.is_valid)()

    if request.GET.get("query") and form_valid:
        response = await create_result_response(request, form)
    else:
        response = await create_form_response(request, form)

    return response


class DicomExplorerView(FormView):
    form_class = DicomExplorerQueryForm

    def get_template_names(self):
        if self.request.GET.get("query"):
            return ["dicom_explorer/dicom_explorer_result.html"]
        else:
            return ["dicom_explorer/dicom_explorer_form.html"]

    def get_form_kwargs(self):
        # Overridden because we use GET method for posting the query

        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if self.request.GET.get("query"):
            kwargs.update({"data": self.request.GET})

        return kwargs

    def post(self, request, *args, **kwargs):
        raise SuspiciousOperation

    def get(self, request, *args, **kwargs):
        if not self.request.GET.get("query"):
            return super().get(request, *args, **kwargs)

        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)

        return self.form_invalid(form)

    def form_valid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
