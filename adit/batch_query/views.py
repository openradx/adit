from io import BytesIO
from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.views import BaseUpdatePreferencesView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.response import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin
from django_tables2 import SingleTableMixin

from adit.core.views import (
    DicomJobCancelView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobDetailView,
    DicomJobListView,
    DicomJobRestartView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomJobVerifyView,
    DicomTaskDeleteView,
    DicomTaskDetailView,
    DicomTaskKillView,
    DicomTaskResetView,
)
from adit.selective_transfer.mixins import SelectiveTransferLockedMixin

from .filters import BatchQueryJobFilter, BatchQueryResultFilter, BatchQueryTaskFilter
from .forms import BatchQueryJobForm
from .mixins import BatchQueryLockedMixin
from .models import BatchQueryJob, BatchQueryTask
from .tables import BatchQueryJobTable, BatchQueryResultTable, BatchQueryTaskTable
from .utils.exporters import write_results

BATCH_QUERY_SOURCE = "batch_query_source"
BATCH_QUERY_URGENT = "batch_query_urgent"
BATCH_QUERY_SEND_FINISHED_MAIL = "batch_query_send_finished_mail"


class BatchQueryUpdatePreferencesView(BatchQueryLockedMixin, BaseUpdatePreferencesView):
    allowed_keys = [
        BATCH_QUERY_SOURCE,
        BATCH_QUERY_URGENT,
        BATCH_QUERY_SEND_FINISHED_MAIL,
    ]


class BatchQueryJobListView(BatchQueryLockedMixin, DicomJobListView):
    model = BatchQueryJob
    table_class = BatchQueryJobTable
    filterset_class = BatchQueryJobFilter
    template_name = "batch_query/batch_query_job_list.html"


class BatchQueryJobCreateView(BatchQueryLockedMixin, DicomJobCreateView):
    model = BatchQueryJob
    form_class = BatchQueryJobForm
    template_name = "batch_query/batch_query_job_form.html"
    permission_required = "batch_query.add_batchqueryjob"
    object: BatchQueryJob

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()

        preferences: dict[str, Any] = self.request.user.preferences

        source = preferences.get(BATCH_QUERY_SOURCE)
        if source is not None:
            initial["source"] = source

        urgent = preferences.get(BATCH_QUERY_URGENT)
        if urgent is not None:
            initial["urgent"] = urgent

        send_finished_mail = preferences.get(BATCH_QUERY_SEND_FINISHED_MAIL)
        if send_finished_mail is not None:
            initial["send_finished_mail"] = send_finished_mail

        return initial

    def form_valid(self, form):
        return super().form_valid(form, settings.START_BATCH_QUERY_UNVERIFIED)


class BatchQueryJobDetailView(BatchQueryLockedMixin, DicomJobDetailView):
    table_class = BatchQueryTaskTable
    filterset_class = BatchQueryTaskFilter
    model = BatchQueryJob
    context_object_name = "job"
    template_name = "batch_query/batch_query_job_detail.html"

    # Overwrite method to also prefetch related results
    def get_filter_queryset(self):
        job = cast(BatchQueryJob, self.get_object())
        return job.tasks.prefetch_related("results")


class BatchQueryJobDeleteView(BatchQueryLockedMixin, DicomJobDeleteView):
    model = BatchQueryJob
    success_url = cast(str, reverse_lazy("batch_query_job_list"))


class BatchQueryJobVerifyView(BatchQueryLockedMixin, DicomJobVerifyView):
    model = BatchQueryJob


class BatchQueryJobCancelView(BatchQueryLockedMixin, DicomJobCancelView):
    model = BatchQueryJob


class BatchQueryJobResumeView(BatchQueryLockedMixin, DicomJobResumeView):
    model = BatchQueryJob


class BatchQueryJobRetryView(BatchQueryLockedMixin, DicomJobRetryView):
    model = BatchQueryJob


class BatchQueryJobRestartView(BatchQueryLockedMixin, DicomJobRestartView):
    model = BatchQueryJob


class BatchQueryTaskDetailView(
    BatchQueryLockedMixin,
    SingleTableMixin,
    PageSizeSelectMixin,
    DicomTaskDetailView,
):
    model = BatchQueryTask
    job_url_name = "batch_query_job_detail"
    template_name = "batch_query/batch_query_task_detail.html"
    table_class = BatchQueryResultTable

    def get_table_data(self):
        task = cast(BatchQueryTask, self.get_object())
        return task.results.all()


class BatchQueryTaskDeleteView(SelectiveTransferLockedMixin, DicomTaskDeleteView):
    model = BatchQueryTask


class BatchQueryTaskResetView(SelectiveTransferLockedMixin, DicomTaskResetView):
    model = BatchQueryTask


class BatchQueryTaskKillView(SelectiveTransferLockedMixin, DicomTaskKillView):
    model = BatchQueryTask


class BatchQueryResultListView(
    BatchQueryLockedMixin,
    LoginRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    table_class = BatchQueryResultTable
    filterset_class = BatchQueryResultFilter
    model = BatchQueryJob
    context_object_name = "job"
    template_name = "batch_query/batch_query_result_list.html"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        assert self.model
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def get_filter_queryset(self):
        job = cast(BatchQueryJob, self.get_object())
        return job.results.select_related("query")


class BatchQueryResultDownloadView(
    BatchQueryLockedMixin,
    LoginRequiredMixin,
    SingleObjectMixin,
    View,
):
    model = BatchQueryJob
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def get(self, request, *args, **kwargs):
        # by overriding get() we have to call get_object() ourselves
        job = cast(BatchQueryJob, self.get_object())
        self.object = job

        file = BytesIO()
        write_results(job, file)

        response = HttpResponse(
            content=file.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filename = f"batch_query_job_{job.pk}_results.xlsx"
        response["Content-Disposition"] = f"attachment;filename={filename}"
        return response
