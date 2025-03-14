import django_filters
from adit_radis_shared.common.forms import SingleFilterFieldFormHelper
from django.http import HttpRequest

from adit.core.filters import DicomJobFilter, DicomTaskFilter

from .models import BatchQueryJob, BatchQueryResult, BatchQueryTask


class BatchQueryJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = BatchQueryJob


class BatchQueryTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = BatchQueryTask


class BatchQueryResultFilter(django_filters.FilterSet):
    task_id = django_filters.NumberFilter(field_name="query_id", label="Task ID")
    request: HttpRequest

    class Meta:
        model = BatchQueryResult
        fields = ("task_id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.form.helper = SingleFilterFieldFormHelper(self.request.GET, "task_id")
