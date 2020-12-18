from adit.core.tables import DicomJobTable, DicomTaskTable
from .models import StudiesFinderJob, StudiesFinderQuery


class StudiesFinderJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = StudiesFinderJob


class StudiesFinderQueryTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = StudiesFinderQuery
