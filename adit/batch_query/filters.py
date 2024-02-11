import django_filters
from django.http import HttpRequest

from adit.core.filters import DicomJobFilter, DicomTaskFilter
from adit.core.forms import FilterSetFormHelper

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

        form_helper = FilterSetFormHelper(self.request.GET)
        form_helper.add_filter_field("task_id", "text", "Filter")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper
