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
from .models import StudyFinderJob, StudyFinderQuery
from .forms import StudyFinderJobForm
from .tables import (
    StudyFinderJobTable,
    StudyFinderQueryTable,
    StudyFinderResultTable,
)
from .filters import (
    StudyFinderJobFilter,
    StudyFinderQueryFilter,
    StudyFinderResultFilter,
)
from .utils.exporters import export_results


class StudyFinderJobListView(DicomJobListView):  # pylint: disable=too-many-ancestors
    model = StudyFinderJob
    table_class = StudyFinderJobTable
    filterset_class = StudyFinderJobFilter
    template_name = "study_finder/study_finder_job_list.html"


class StudyFinderJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UrgentFormViewMixin,
    CreateView,
):
    model = StudyFinderJob
    form_class = StudyFinderJobForm
    template_name = "study_finder/study_finder_job_form.html"
    permission_required = "study_finder.add_studyfinderjob"


class StudyFinderJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    owner_accessor = "owner"
    table_class = StudyFinderQueryTable
    filterset_class = StudyFinderQueryFilter
    model = StudyFinderJob
    context_object_name = "job"
    template_name = "study_finder/study_finder_job_detail.html"

    def get_filter_queryset(self):
        job = self.get_object()
        return job.queries.prefetch_related("results")


class StudyFinderJobDeleteView(DicomJobDeleteView):
    model = StudyFinderJob
    success_url = reverse_lazy("batch_transfer_job_list")


class StudyFinderJobCancelView(DicomJobCancelView):
    model = StudyFinderJob


class StudyFinderJobVerifyView(DicomJobVerifyView):
    model = StudyFinderJob


# TODO remove
class StudyFinderQueryDetailView(
    SingleTableMixin,
    PageSizeSelectMixin,
    DicomTaskDetailView,
):
    model = StudyFinderQuery
    context_object_name = "query"
    job_url_name = "study_finder_job_detail"
    template_name = "study_finder/study_finder_query_detail.html"
    table_class = StudyFinderResultTable

    def get_table_data(self):
        return self.object.results.all()


class StudyFinderResultListView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    owner_accessor = "owner"
    table_class = StudyFinderResultTable
    filterset_class = StudyFinderResultFilter
    model = StudyFinderJob
    context_object_name = "job"
    template_name = "study_finder/study_finder_result_list.html"

    def get_filter_queryset(self):
        return self.object.results.select_related("query")


class StudyFinderResultDownloadView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleObjectMixin,
    View,
):
    model = StudyFinderJob
    owner_accessor = "owner"

    def get(self, request):
        job = self.get_object()
        file = StringIO()
        export_results(job, file)
        response = HttpResponse(file, content_type="text/csv")
        filename = f"study_finder_job_{job.id}_results.csv"
        response["Content-Disposition"] = f"attachment;filename={filename}"
        return response
