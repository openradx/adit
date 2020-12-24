from adit.core.filters import DicomJobFilter, DicomTaskFilter
from .models import StudyFinderJob, StudyFinderQuery


class StudyFinderJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = StudyFinderJob


class StudyFinderQueryFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = StudyFinderQuery
