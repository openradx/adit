import django_filters
from adit_radis_shared.common.forms import SingleFilterFieldFormHelper
from django.http import HttpRequest

from .models import DicomJob, DicomTask


class DicomJobFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model: type[DicomJob]
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.form.helper = SingleFilterFieldFormHelper(self.request.GET, "status")


class DicomTaskFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model: type[DicomTask]
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.form.helper = SingleFilterFieldFormHelper(self.request.GET, "status")
