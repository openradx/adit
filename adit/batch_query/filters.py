import django_filters
from django.views import View

from adit.core.filters import DicomJobFilter, DicomTaskFilter
from adit.core.forms import SingleFilterFormHelper
from adit.core.utils.type_utils import with_type_hint

from .models import BatchQueryJob, BatchQueryResult, BatchQueryTask


class BatchQueryJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = BatchQueryJob


class BatchQueryTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = BatchQueryTask


class BatchQueryResultFilter(django_filters.FilterSet, with_type_hint(View)):
    task_id = django_filters.NumberFilter(field_name="query__task_id", label="Task ID")

    class Meta:
        model = BatchQueryResult
        fields = ("task_id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = SingleFilterFormHelper(
            self.request.GET,
            "task_id",
            select_widget=False,
            custom_style="width: 7em;",
        )
