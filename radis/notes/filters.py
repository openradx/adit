import django_filters

from radis.core.forms import FilterSetFormHelper

from .models import Note


class NoteFilter(django_filters.FilterSet):
    text = django_filters.CharFilter(lookup_expr="search", label="Search Notes")

    class Meta:
        model = Note
        fields = ("text",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        form_helper = FilterSetFormHelper(self.data)
        form_helper.add_filter_field("text", "text", "Search")
        form_helper.build_filter_set_layout()
        self.form.helper = form_helper
