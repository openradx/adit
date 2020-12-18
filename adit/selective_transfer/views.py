from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.http import HttpResponseBadRequest
from django.urls import reverse_lazy
from django_tables2 import SingleTableMixin
from adit.core.mixins import (
    OwnerRequiredMixin,
    UrgentFormViewMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
)
from adit.core.views import (
    TransferJobListView,
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

QUERY_RESULT_LIMIT = 101


class SelectiveTransferJobListView(
    TransferJobListView
):  # pylint: disable=too-many-ancestors
    model = SelectiveTransferJob
    table_class = SelectiveTransferJobTable
    filterset_class = SelectiveTransferJobFilter
    template_name = "selective_transfer/selective_transfer_job_list.html"


class SelectiveTransferJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SelectiveTransferJobCreateMixin,
    UrgentFormViewMixin,
    CreateView,
):
    """A view class to render the selective transfer form.

    POST (and the creation of the job) is not handled by this view because the
    job itself is created by using the REST API and an AJAX call.
    """

    template_name = "selective_transfer/selective_transfer_job_form.html"
    form_class = SelectiveTransferJobForm
    permission_required = "selective_transfer.add_selectivetransferjob"

    def form_invalid(self, form):
        error_message = "Please correct the form errors and search again."
        return self.render_to_response(
            self.get_context_data(form=form, error_message=error_message)
        )

    def form_valid(self, form):
        action = self.request.POST.get("action")

        if action == "query":
            connector = self.create_source_connector(form)
            studies = self.query_studies(connector, form, QUERY_RESULT_LIMIT)

            max_query_results = len(studies) >= QUERY_RESULT_LIMIT

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
    owner_accessor = "owner"
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
