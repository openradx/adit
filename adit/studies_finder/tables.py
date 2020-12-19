import django_tables2 as tables
from adit.core.tables import DicomJobTable, DicomTaskTable
from .models import StudiesFinderJob, StudiesFinderQuery, StudiesFinderResult


class StudiesFinderJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = StudiesFinderJob


class StudiesFinderQueryTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = StudiesFinderQuery


class StudiesFinderResultTable(tables.Table):
    class Meta:  # pylint: disable=too-few-public-methods
        model = StudiesFinderResult
        template_name = "django_tables2/bootstrap4.html"
        fields = (
            "study_date",
            "study_description",
            "modalities",
            "image_count",
            "accession_number",
        )
        attrs = {
            "id": "studies_finder_result_table",
            "class": "table table-bordered table-hover",
        }
