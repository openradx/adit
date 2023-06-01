import django_filters
from django.views import View

from adit.core.forms import MultiInlineFilterFormHelper, SingleFilterFormHelper
from adit.core.utils.type_utils import with_type_hint


class DicomJobFilter(django_filters.FilterSet, with_type_hint(View)):
    class Meta:
        model = None
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = MultiInlineFilterFormHelper(self.request.GET, self.Meta.fields)


class DicomTaskFilter(django_filters.FilterSet, with_type_hint(View)):
    class Meta:
        model = None
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = SingleFilterFormHelper(self.request.GET, self.Meta.fields[0])
