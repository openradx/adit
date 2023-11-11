from datetime import datetime
from typing import Any

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.urls import reverse_lazy

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

from .filters import SelectiveTransferJobFilter, SelectiveTransferTaskFilter
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferJobCreateMixin, SelectiveTransferLockedMixin
from .models import SelectiveTransferJob, SelectiveTransferTask
from .tables import SelectiveTransferJobTable, SelectiveTransferTaskTable

SELECTIVE_TRANSFER_SOURCE = "selective_transfer_source"
SELECTIVE_TRANSFER_DESTINATION = "selective_transfer_destination"
SELECTIVE_TRANSFER_URGENT = "selective_transfer_urgent"
SELECTIVE_TRANSFER_SEND_FINISHED_MAIL = "selective_transfer_send_finished_mail"
SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED = "selective_transfer_advanced_options_collapsed"


class SelectiveTransferUpdatePreferencesView(
    SelectiveTransferLockedMixin, BaseUpdatePreferencesView
):
    allowed_keys = [
        SELECTIVE_TRANSFER_SOURCE,
        SELECTIVE_TRANSFER_DESTINATION,
        SELECTIVE_TRANSFER_URGENT,
        SELECTIVE_TRANSFER_SEND_FINISHED_MAIL,
        SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED,
    ]


class SelectiveTransferJobListView(SelectiveTransferLockedMixin, TransferJobListView):
    model = SelectiveTransferJob
    table_class = SelectiveTransferJobTable
    filterset_class = SelectiveTransferJobFilter
    template_name = "selective_transfer/selective_transfer_job_list.html"


class SelectiveTransferJobCreateView(
    SelectiveTransferLockedMixin, SelectiveTransferJobCreateMixin, DicomJobCreateView
):
    """A view class to render the selective transfer form.

    POST (and the creation of the job) is not handled by this view because the
    job itself is created by using the REST API and an AJAX call.

    TODO: Maybe we should only use this view to render the form and not for processing
    it as normally we use the WebSocket consumer for that. It is a relict and a
    fallback when no JavaScript or WebSockets are available.
    """

    form_class = SelectiveTransferJobForm
    template_name = "selective_transfer/selective_transfer_job_form.html"
    permission_required = "selective_transfer.add_selectivetransferjob"

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()

        kwargs["action"] = self.request.POST.get("action")

        preferences: dict[str, Any] = self.request.user.preferences
        kwargs["advanced_options_collapsed"] = preferences.get(
            SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED, False
        )

        return kwargs

    def get_initial(self):
        initial = super().get_initial()

        preferences: dict[str, Any] = self.request.user.preferences

        source = preferences.get(SELECTIVE_TRANSFER_SOURCE)
        if source is not None:
            initial["source"] = source

        destination = preferences.get(SELECTIVE_TRANSFER_DESTINATION)
        if destination is not None:
            initial["destination"] = destination

        urgent = preferences.get(SELECTIVE_TRANSFER_URGENT)
        if urgent is not None:
            initial["urgent"] = urgent

        send_finished_mail = preferences.get(SELECTIVE_TRANSFER_SEND_FINISHED_MAIL)
        if send_finished_mail is not None:
            initial["send_finished_mail"] = send_finished_mail

        return initial

    def form_invalid(self, form):
        error_message = "Please correct the form errors and search again."
        return self.render_to_response(
            self.get_context_data(form=form, error_message=error_message)
        )

    def form_valid(self, form: SelectiveTransferJobForm):
        action = self.request.POST.get("action")

        if action == "query":
            connector = self.create_source_operator(form)
            limit = settings.SELECTIVE_TRANSFER_RESULT_LIMIT
            studies = list(self.query_studies(connector, form, limit))
            studies = sorted(
                studies,
                key=lambda study: datetime.combine(study.StudyDate, study.StudyTime),
                reverse=True,
            )
            max_results_reached = len(studies) >= limit
            return self.render_to_response(
                self.get_context_data(
                    query=True,
                    query_results=studies,
                    max_results_reached=max_results_reached,
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


class SelectiveTransferJobDetailView(SelectiveTransferLockedMixin, DicomJobDetailView):
    table_class = SelectiveTransferTaskTable
    filterset_class = SelectiveTransferTaskFilter
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"


class SelectiveTransferJobDeleteView(SelectiveTransferLockedMixin, DicomJobDeleteView):
    model = SelectiveTransferJob
    success_url = reverse_lazy("selective_transfer_job_list")


class SelectiveTransferJobVerifyView(SelectiveTransferLockedMixin, DicomJobVerifyView):
    model = SelectiveTransferJob
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY


class SelectiveTransferJobCancelView(SelectiveTransferLockedMixin, DicomJobCancelView):
    model = SelectiveTransferJob


class SelectiveTransferJobResumeView(SelectiveTransferLockedMixin, DicomJobResumeView):
    model = SelectiveTransferJob
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY


class SelectiveTransferJobRetryView(SelectiveTransferLockedMixin, DicomJobRetryView):
    model = SelectiveTransferJob
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY


class SelectiveTransferJobRestartView(SelectiveTransferLockedMixin, DicomJobRestartView):
    model = SelectiveTransferJob
    default_priority = settings.SELECTIVE_TRANSFER_DEFAULT_PRIORITY
    urgent_priority = settings.SELECTIVE_TRANSFER_URGENT_PRIORITY


class SelectiveTransferTaskDetailView(SelectiveTransferLockedMixin, DicomTaskDetailView):
    model = SelectiveTransferTask
    job_url_name = "selective_transfer_job_detail"
    template_name = "selective_transfer/selective_transfer_task_detail.html"
