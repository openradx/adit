import django_tables2 as tables
from adit.core.tables import DicomJobTable, BatchTaskTable
from .models import BatchQueryJob, BatchQueryTask, BatchQueryResult


class BatchQueryJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchQueryJob


class BatchQueryTaskTable(BatchTaskTable):
    class Meta(BatchTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchQueryTask
        empty_text = "No queries to show"


class BatchQueryResultTable(tables.Table):
    batch_id = tables.Column(accessor="query__batch_id", verbose_name="Batch ID")
    study_date_time = tables.DateTimeColumn(
        verbose_name="Study Date/Time", order_by=("study_date", "study_time")
    )
    image_count = tables.Column(verbose_name="# Images")

    class Meta:  # pylint: disable=too-few-public-methods
        model = BatchQueryResult
        template_name = "django_tables2/bootstrap4.html"
        empty_text = "No results to show"
        fields = (
            "batch_id",
            "study_date_time",
            "study_description",
            "modalities",
            "image_count",
            "accession_number",
        )
        attrs = {
            "id": "batch_query_result_table",
            "class": "table table-bordered table-hover",
        }

    def render_modalities(self, value):
        return ", ".join(value)
