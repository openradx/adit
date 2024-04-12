from typing import Any

from django.core.exceptions import BadRequest
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
    DicomTaskDeleteView,
    DicomTaskDetailView,
    DicomTaskKillView,
    DicomTaskResetView,
    TransferJobListView,
)
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.views import BaseUpdatePreferencesView

from .filters import SelectiveTransferJobFilter, SelectiveTransferTaskFilter
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferLockedMixin
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


class SelectiveTransferJobCreateView(SelectiveTransferLockedMixin, DicomJobCreateView):
    """A view class to render the selective transfer form.

    The form data itself is not processed by this view but by using WebSockets (see
    consumer.py). That way long running queries and cancellation can be used.
    """

    form_class = SelectiveTransferJobForm
    template_name = "selective_transfer/selective_transfer_job_form.html"
    permission_required = "selective_transfer.add_selectivetransferjob"
    request: AuthenticatedHttpRequest

    def post(self, request, *args, **kwargs):
        raise BadRequest("Form is only for use with WebSockets")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()

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


class SelectiveTransferJobCancelView(SelectiveTransferLockedMixin, DicomJobCancelView):
    model = SelectiveTransferJob


class SelectiveTransferJobResumeView(SelectiveTransferLockedMixin, DicomJobResumeView):
    model = SelectiveTransferJob


class SelectiveTransferJobRetryView(SelectiveTransferLockedMixin, DicomJobRetryView):
    model = SelectiveTransferJob


class SelectiveTransferJobRestartView(SelectiveTransferLockedMixin, DicomJobRestartView):
    model = SelectiveTransferJob


class SelectiveTransferTaskDetailView(SelectiveTransferLockedMixin, DicomTaskDetailView):
    model = SelectiveTransferTask
    job_url_name = "selective_transfer_job_detail"
    template_name = "selective_transfer/selective_transfer_task_detail.html"


class SelectiveTransferTaskDeleteView(SelectiveTransferLockedMixin, DicomTaskDeleteView):
    model = SelectiveTransferTask


class SelectiveTransferTaskResetView(SelectiveTransferLockedMixin, DicomTaskResetView):
    model = SelectiveTransferTask


class SelectiveTransferTaskKillView(SelectiveTransferLockedMixin, DicomTaskKillView):
    model = SelectiveTransferTask
