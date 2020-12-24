import django_tables2 as tables
from adit.core.tables import DicomJobTable, DicomTaskTable
from .models import StudyFinderJob, StudyFinderQuery, StudyFinderResult


class StudyFinderJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = StudyFinderJob


class StudyFinderQueryTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = StudyFinderQuery
        empty_text = "No queries to show"


class StudyFinderResultTable(tables.Table):
    class Meta:  # pylint: disable=too-few-public-methods
        model = StudyFinderResult
        template_name = "django_tables2/bootstrap4.html"
        empty_text = "No results to show"
        fields = (
            "study_date",
            "study_description",
            "modalities",
            "image_count",
            "accession_number",
        )
        attrs = {
            "id": "study_finder_result_table",
            "class": "table table-bordered table-hover",
        }

    def render_modalities(self, value):
        return ", ".join(value)
