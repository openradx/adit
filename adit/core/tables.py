from django.utils.html import format_html
import django_tables2 as tables
from .templatetags.core_extras import (
    dicom_job_status_css_class,
    dicom_task_status_css_class,
)


class RecordIdColumn(tables.Column):
    attrs = {"td": {"class": "record-id"}}

    def render(self, record, value):  # pylint: disable=arguments-differ
        url = record.get_absolute_url()
        return format_html(f'<a href="{url}">{value}</a>')


class DicomJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")

    class Meta:  # pylint: disable=too-few-public-methods
        model = None
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "status", "source", "created")
        empty_text = "No jobs to show"
        attrs = {
            "id": "dicom_job_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        css_class = dicom_job_status_css_class(record.status)
        return format_html(f'<span class="{css_class}">{value}</span>')


class TransferJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):  # pylint: disable=too-few-public-methods
        fields = ("id", "status", "source", "destination", "created")


class DicomTaskTable(tables.Table):
    id = RecordIdColumn(verbose_name="Task ID")
    end = tables.DateTimeColumn(verbose_name="Finished At")

    class Meta:  # pylint: disable=too-few-public-methods
        model = None
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "status", "message", "end")
        empty_text = "No tasks to show"
        attrs = {
            "id": "dicom_task_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        css_class = dicom_task_status_css_class(record.status)
        return format_html(f'<span class="{css_class}">{value}</span>')
