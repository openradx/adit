from adit_radis_shared.common.mixins import PageSizeSelectMixin
from django.db.models import QuerySet
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import RouterJobFilter
from .mixins import RouterStaffRequiredMixin
from .models import RouterJob
from .tables import RouterJobTable


class RouterJobListView(
    RouterStaffRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    model = RouterJob
    table_class = RouterJobTable
    filterset_class = RouterJobFilter
    template_name = "router/router_job_list.html"

    def get_queryset(self) -> QuerySet[RouterJob]:
        # Staff see every router job, so the Admin Section's ?all=1 changes nothing here.
        return RouterJob.objects.select_related("rule").order_by("-created")
