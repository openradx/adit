from typing import Any, Dict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from django.http import HttpResponseBadRequest
from django.urls import reverse_lazy
from django.conf import settings
from django_tables2 import SingleTableMixin
from adit.core.mixins import (
    OwnerRequiredMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
)
from adit.core.views import (
    TransferJobListView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobCancelView,
    DicomJobVerifyView,
    DicomTaskDetailView,
)
from .forms import SelectiveTransferJobForm
from .models import SelectiveTransferJob, SelectiveTransferTask
from .mixins import SelectiveTransferJobCreateMixin
from .tables import SelectiveTransferJobTable, SelectiveTransferTaskTable
from .filters import SelectiveTransferJobFilter, SelectiveTransferTaskFilter


class SelectiveTransferJobListView(
    TransferJobListView
):  # pylint: disable=too-many-ancestors
    model = SelectiveTransferJob
    table_class = SelectiveTransferJobTable
    filterset_class = SelectiveTransferJobFilter
    template_name = "selective_transfer/selective_transfer_job_list.html"


class SelectiveTransferJobCreateView(
    SelectiveTransferJobCreateMixin,
    DicomJobCreateView,
):
    """A view class to render the selective transfer form.

    POST (and the creation of the job) is not handled by this view because the
    job itself is created by using the REST API and an AJAX call.
    """

    form_class = SelectiveTransferJobForm
    template_name = "selective_transfer/selective_transfer_job_form.html"
    permission_required = "selective_transfer.add_selectivetransferjob"

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()

        action = self.request.POST.get("action")
        kwargs.update({"query_form": action == "query"})

        return kwargs

    def form_invalid(self, form):
        error_message = "Please correct the form errors and search again."
        return self.render_to_response(
            self.get_context_data(form=form, error_message=error_message)
        )

    def form_valid(self, form):
        action = self.request.POST.get("action")

        if action == "query":
            connector = self.create_source_connector(form)
            limit = settings.SELECTIVE_TRANSFER_RESULT_LIMIT
            studies = self.query_studies(connector, form, limit)
            max_query_results = len(studies) >= limit
            return self.render_to_response(
                self.get_context_data(
                    query=True,
                    query_results=studies,
                    max_query_results=max_query_results,
                )
            )

        if action == "transfer":
            user = self.request.user
            selected_studies = self.request.POST.getlist("selected_studies")
            try:
                job = self.transfer_selected_studies(user, form, selected_studies)
            except ValueError as err:
                return self.render_to_response(
                    self.get_context_data(transfer=True, error_message=str(err))
                )
            return self.render_to_response(
                self.get_context_data(transfer=True, created_job=job)
            )

        return HttpResponseBadRequest()


class SelectiveTransferJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    table_class = SelectiveTransferTaskTable
    filterset_class = SelectiveTransferTaskFilter
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"

    def get_filter_queryset(self):
        job = self.get_object()
        return job.tasks


class SelectiveTransferJobDeleteView(DicomJobDeleteView):
    model = SelectiveTransferJob
    success_url = reverse_lazy("selective_transfer_job_list")


class SelectiveTransferJobCancelView(DicomJobCancelView):
    model = SelectiveTransferJob


class SelectiveTransferJobVerifyView(DicomJobVerifyView):
    model = SelectiveTransferJob


class SelectiveTransferTaskDetailView(DicomTaskDetailView):
    model = SelectiveTransferTask
    job_url_name = "selective_transfer_job_detail"
    template_name = "selective_transfer/selective_transfer_task_detail.html"
