from io import StringIO
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.response import HttpResponse
from django.views.generic import DetailView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.base import View
from django.urls import reverse_lazy
from django.conf import settings
from django_tables2 import SingleTableMixin
from adit.core.mixins import (
    OwnerRequiredMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
)
from adit.core.views import (
    DicomJobListView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobVerifyView,
    DicomJobCancelView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomTaskDetailView,
)
from .models import BatchQueryJob, BatchQueryTask
from .forms import BatchQueryJobForm
from .tables import (
    BatchQueryJobTable,
    BatchQueryTaskTable,
    BatchQueryResultTable,
)
from .filters import (
    BatchQueryJobFilter,
    BatchQueryTaskFilter,
    BatchQueryResultFilter,
)
from .utils.exporters import export_results


class BatchQueryJobListView(DicomJobListView):  # pylint: disable=too-many-ancestors
    model = BatchQueryJob
    table_class = BatchQueryJobTable
    filterset_class = BatchQueryJobFilter
    template_name = "batch_query/batch_query_job_list.html"


class BatchQueryJobCreateView(DicomJobCreateView):
    model = BatchQueryJob
    form_class = BatchQueryJobForm
    template_name = "batch_query/batch_query_job_form.html"
    permission_required = "batch_query.add_batchqueryjob"

    def form_valid(self, form):
        user = self.request.user
        form.instance.owner = user

        response = super().form_valid(form)

        job = self.object
        if user.is_staff or settings.BATCH_QUERY_UNVERIFIED:
            job.status = BatchQueryJob.Status.PENDING
            job.save()
            job.delay()

        return response


class BatchQueryJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    table_class = BatchQueryTaskTable
    filterset_class = BatchQueryTaskFilter
    model = BatchQueryJob
    context_object_name = "job"
    template_name = "batch_query/batch_query_job_detail.html"

    def get_filter_queryset(self):
        job = self.get_object()
        return job.tasks.prefetch_related("results")


class BatchQueryJobDeleteView(DicomJobDeleteView):
    model = BatchQueryJob
    success_url = reverse_lazy("batch_transfer_job_list")


class BatchQueryJobVerifyView(DicomJobVerifyView):
    model = BatchQueryJob


class BatchQueryJobCancelView(DicomJobCancelView):
    model = BatchQueryJob


class BatchQueryJobResumeView(DicomJobResumeView):
    model = BatchQueryJob


class BatchQueryJobRetryView(DicomJobRetryView):
    model = BatchQueryJob


class BatchQueryTaskDetailView(
    SingleTableMixin,
    PageSizeSelectMixin,
    DicomTaskDetailView,
):
    model = BatchQueryTask
    job_url_name = "batch_query_job_detail"
    template_name = "batch_query/batch_query_task_detail.html"
    table_class = BatchQueryResultTable

    def get_table_data(self):
        return self.object.results.all()


class BatchQueryResultListView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
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

    def get_filter_queryset(self):
        return self.object.results.select_related("query")


class BatchQueryResultDownloadView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleObjectMixin,
    View,
):
    model = BatchQueryJob

    def get(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        job = self.get_object()
        file = StringIO()
        export_results(job, file)

        # We use CP-1252 (ANSI) charset so that the exported CSV files could be
        # directly opened in Excel under Windows and Umlaute are correctly presented.
        content = file.getvalue().encode("cp1252")

        response = HttpResponse(content, content_type="text/csv")
        filename = f"batch_query_job_{job.id}_results.csv"
        response["Content-Disposition"] = f"attachment;filename={filename}"
        return response
