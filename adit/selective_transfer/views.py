from typing import Any, Dict

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.urls import reverse_lazy

from adit.core.views import (
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

from .filters import SelectiveTransferJobFilter, SelectiveTransferTaskFilter
from .forms import SelectiveTransferJobForm
from .mixins import (
    SAVED_DESTINATION_FIELD,
    SAVED_SOURCE_FIELD,
    SAVED_URGENT_FIELD,
    SelectiveTransferJobCreateMixin,
)
from .models import SelectiveTransferJob, SelectiveTransferTask
from .tables import SelectiveTransferJobTable, SelectiveTransferTaskTable


class SelectiveTransferJobListView(TransferJobListView):
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
        kwargs.update({"action": action})

        return kwargs

    def get_initial(self):
        initial = super().get_initial()

        # Restore source, destination and urgency from last submit

        saved_source = self.request.session.get(SAVED_SOURCE_FIELD)
        if saved_source is not None:
            initial.update({"source": saved_source})

        saved_destination = self.request.session.get(SAVED_DESTINATION_FIELD)
        if saved_destination is not None:
            initial.update({"destination": saved_destination})

        urgent = self.request.session.get(SAVED_URGENT_FIELD)
        if urgent is not None:
            initial.update({"urgent": urgent})

        return initial

    def form_invalid(self, form):
        error_message = "Please correct the form errors and search again."
        return self.render_to_response(
            self.get_context_data(form=form, error_message=error_message)
        )

    def form_valid(self, form: SelectiveTransferJobForm):
        self.save_initial_form_data(self.request.session, form)

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
            return self.render_to_response(self.get_context_data(transfer=True, created_job=job))

        return HttpResponseBadRequest()


class SelectiveTransferJobDetailView(DicomJobDetailView):
    table_class = SelectiveTransferTaskTable
    filterset_class = SelectiveTransferTaskFilter
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"


class SelectiveTransferJobDeleteView(DicomJobDeleteView):
    model = SelectiveTransferJob
    success_url = reverse_lazy("selective_transfer_job_list")


class SelectiveTransferJobVerifyView(DicomJobVerifyView):
    model = SelectiveTransferJob


class SelectiveTransferJobCancelView(DicomJobCancelView):
    model = SelectiveTransferJob


class SelectiveTransferJobResumeView(DicomJobResumeView):
    model = SelectiveTransferJob


class SelectiveTransferJobRetryView(DicomJobRetryView):
    model = SelectiveTransferJob


class SelectiveTransferJobRestartView(DicomJobRestartView):
    model = SelectiveTransferJob


class SelectiveTransferTaskDetailView(DicomTaskDetailView):
    model = SelectiveTransferTask
    job_url_name = "selective_transfer_job_detail"
    template_name = "selective_transfer/selective_transfer_task_detail.html"
