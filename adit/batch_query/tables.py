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
    study_date_time = tables.DateTimeColumn(
        verbose_name="Study Date/Time", order_by=("study_date", "study_time")
    )
    image_count = tables.Column(verbose_name="# Images")

    class Meta:
        model = BatchQueryResult
        empty_text = "No results to show"
        fields = (
            "task_id",
            "patient_id",
            "study_date_time",
            "study_description",
            "modalities",
            "image_count",
        )
        attrs = {
            "id": "batch_query_result_table",
            "class": "table table-bordered table-hover",
        }
