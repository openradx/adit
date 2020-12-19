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
from .models import StudiesFinderJob, StudiesFinderQuery
from .forms import StudiesFinderJobForm
from .tables import (
    StudiesFinderJobTable,
    StudiesFinderQueryTable,
    StudiesFinderResultTable,
)
from .filters import StudiesFinderJobFilter, StudiesFinderQueryFilter


class StudiesFinderJobListView(DicomJobListView):  # pylint: disable=too-many-ancestors
    model = StudiesFinderJob
    table_class = StudiesFinderJobTable
    filterset_class = StudiesFinderJobFilter
    template_name = "studies_finder/studies_finder_job_list.html"


class StudiesFinderJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UrgentFormViewMixin,
    CreateView,
):
    model = StudiesFinderJob
    form_class = StudiesFinderJobForm
    template_name = "studies_finder/studies_finder_job_form.html"
    permission_required = "studies_finder.add_studiesfinderjob"


class StudiesFinderJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    owner_accessor = "owner"
    table_class = StudiesFinderQueryTable
    filterset_class = StudiesFinderQueryFilter
    model = StudiesFinderJob
    context_object_name = "job"
    template_name = "studies_finder/studies_finder_job_detail.html"

    def get_filter_queryset(self):
        job = self.get_object()
        return job.queries.prefetch_related("results")


class StudiesFinderJobDeleteView(DicomJobDeleteView):
    model = StudiesFinderJob
    success_url = reverse_lazy("batch_transfer_job_list")


class StudiesFinderJobCancelView(DicomJobCancelView):
    model = StudiesFinderJob


class StudiesFinderJobVerifyView(DicomJobVerifyView):
    model = StudiesFinderJob


class StudiesFinderQueryDetailView(
    SingleTableMixin,
    PageSizeSelectMixin,
    DicomTaskDetailView,
):
    model = StudiesFinderQuery
    job_url_name = "studies_finder_job_detail"
    template_name = "studies_finder/studies_finder_query_detail.html"
    table_class = StudiesFinderResultTable

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.object:
            # table_data is consumed by SingleTableMixin of django_tables2
            self.table_data = self.object.results

        return context


def studies_finder_results_download_view(request):
    raise NotImplementedError()
