from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
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
from .models import StudyFinderJob, StudyFinderQuery, StudyFinderResult
from .forms import StudyFinderJobForm
from .tables import (
    StudyFinderJobTable,
    StudyFinderQueryTable,
    StudyFinderResultTable,
)
from .filters import StudyFinderJobFilter, StudyFinderQueryFilter


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


def study_finder_results_download_view(request):
    raise NotImplementedError()
