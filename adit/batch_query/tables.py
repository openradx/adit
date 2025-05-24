import django_tables2 as tables

from adit.core.tables import DicomJobTable, DicomTaskTable

from .models import BatchQueryJob, BatchQueryResult, BatchQueryTask


class BatchQueryJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):
        model = BatchQueryJob


class BatchQueryTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = BatchQueryTask
        empty_text = "No queries to show"


class BatchQueryResultTable(tables.Table):
    task_id = tables.Column(accessor="query_id", verbose_name="Task ID")
    patient_id = tables.Column(verbose_name="Patient ID")
    study_datetime = tables.DateTimeColumn(verbose_name="Study Date/Time")
    study_description = tables.Column(verbose_name="Study Description")
    image_count = tables.Column(verbose_name="# Images")

    class Meta:
        model = BatchQueryResult
        empty_text = "No results to show"
        fields = (
            "task_id",
            "patient_id",
            "study_datetime",
            "study_description",
            "modalities",
            "image_count",
        )
        attrs = {
            "id": "batch_query_result_table",
            "class": "table table-bordered table-hover",
        }

    def render_modalities(self, value: list[str], record):
        return ", ".join(value)
