from adit.core.filters import DicomJobFilter, DicomTaskFilter
from .models import StudiesFinderJob, StudiesFinderQuery


class StudiesFinderJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = StudiesFinderJob


class StudiesFinderQueryFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = StudiesFinderQuery
