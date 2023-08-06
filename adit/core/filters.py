import django_filters
from django.views import View

from adit.core.forms import FilterSetFormHelper
from adit.core.utils.type_utils import with_type_hint

from .models import DicomJob, DicomTask


class DicomJobFilter(django_filters.FilterSet, with_type_hint(View)):
    class Meta:
        model: type[DicomJob]
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        form_helper = FilterSetFormHelper(self.request.GET)
        form_helper.add_filter_field("status", "select", "Filter")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper


class DicomTaskFilter(django_filters.FilterSet, with_type_hint(View)):
    class Meta:
        model: type[DicomTask]
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        form_helper = FilterSetFormHelper(self.request.GET)
        form_helper.add_filter_field("status", "select", "Filter")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper
