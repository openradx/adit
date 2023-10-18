import django_filters

from radis.core.forms import FilterSetFormHelper

from .models import Collection


class CollectionFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="search")

    class Meta:
        model = Collection
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        form_helper = FilterSetFormHelper(self.data)
        form_helper.add_filter_field("name", "text", "Filter")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper
