from io import StringIO
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http.response import HttpResponse
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.base import View
from django.urls import reverse_lazy
from django_tables2 import SingleTableMixin
from adit.core.mixins import (
    OwnerRequiredMixin,
    UrgentFormViewMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
)
from adit.core.views import (
    DicomJobListView,
    DicomJobDeleteView,
    DicomJobCancelView,
    DicomJobVerifyView,
    DicomTaskDetailView,
)
from .models import BatchFinderJob, BatchFinderQuery
from .forms import BatchFinderJobForm
from .tables import (
    BatchFinderJobTable,
    BatchFinderQueryTable,
    BatchFinderResultTable,
)
from .filters import (
    BatchFinderJobFilter,
    BatchFinderQueryFilter,
    BatchFinderResultFilter,
)
from .utils.exporters import export_results


class BatchFinderJobListView(DicomJobListView):  # pylint: disable=too-many-ancestors
    model = BatchFinderJob
    table_class = BatchFinderJobTable
    filterset_class = BatchFinderJobFilter
    template_name = "batch_finder/batch_finder_job_list.html"


class BatchFinderJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UrgentFormViewMixin,
    CreateView,
):
    model = BatchFinderJob
    form_class = BatchFinderJobForm
    template_name = "batch_finder/batch_finder_job_form.html"
    permission_required = "batch_finder.add_batchfinderjob"


class BatchFinderJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    owner_accessor = "owner"
    table_class = BatchFinderQueryTable
    filterset_class = BatchFinderQueryFilter
    model = BatchFinderJob
    context_object_name = "job"
    template_name = "batch_finder/batch_finder_job_detail.html"

    def get_filter_queryset(self):
        job = self.get_object()
        return job.queries.prefetch_related("results")


class BatchFinderJobDeleteView(DicomJobDeleteView):
    model = BatchFinderJob
    success_url = reverse_lazy("batch_transfer_job_list")


class BatchFinderJobCancelView(DicomJobCancelView):
    model = BatchFinderJob


class BatchFinderJobVerifyView(DicomJobVerifyView):
    model = BatchFinderJob


# TODO remove
class BatchFinderQueryDetailView(
    SingleTableMixin,
    PageSizeSelectMixin,
    DicomTaskDetailView,
):
    model = BatchFinderQuery
    context_object_name = "query"
    job_url_name = "batch_finder_job_detail"
    template_name = "batch_finder/batch_finder_query_detail.html"
    table_class = BatchFinderResultTable

    def get_table_data(self):
        return self.object.results.all()


class BatchFinderResultListView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    owner_accessor = "owner"
    table_class = BatchFinderResultTable
    filterset_class = BatchFinderResultFilter
    model = BatchFinderJob
    context_object_name = "job"
    template_name = "batch_finder/batch_finder_result_list.html"

    def get_filter_queryset(self):
        return self.object.results.select_related("query")


class BatchFinderResultDownloadView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleObjectMixin,
    View,
):
    model = BatchFinderJob
    owner_accessor = "owner"

    def get(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        job = self.get_object()
        file = StringIO()
        export_results(job, file)
        response = HttpResponse(file.getvalue(), content_type="text/csv")
        filename = f"batch_finder_job_{job.id}_results.csv"
        response["Content-Disposition"] = f"attachment;filename={filename}"
        return response
