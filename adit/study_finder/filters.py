import django_filters
from adit.core.filters import DicomJobFilter, DicomTaskFilter
from adit.core.forms import SingleFilterFormHelper
from .models import StudyFinderJob, StudyFinderQuery, StudyFinderResult


class StudyFinderJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = StudyFinderJob


class StudyFinderQueryFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = StudyFinderQuery


class StudyFinderResultFilter(django_filters.FilterSet):
    batch_id = django_filters.NumberFilter(
        field_name="query__batch_id", label="Batch ID"
    )

    class Meta:
        model = StudyFinderResult
        fields = ("batch_id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = SingleFilterFormHelper(
            self.request.GET,
            "batch_id",
            select_widget=False,
            custom_style="width: 7em;",
        )
