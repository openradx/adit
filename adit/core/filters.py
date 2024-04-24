import django_filters
from adit_radis_shared.common.forms import FilterSetFormHelper
from django.http import HttpRequest

from .models import DicomJob, DicomTask


class DicomJobFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model: type[DicomJob]
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        form_helper = FilterSetFormHelper(self.request.GET)
        form_helper.add_filter_field("status", "select", "Filter")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper


class DicomTaskFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model: type[DicomTask]
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        form_helper = FilterSetFormHelper(self.request.GET)
        form_helper.add_filter_field("status", "select", "Filter")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper
