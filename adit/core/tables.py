import django_tables2 as tables
from django.utils.html import format_html

from .templatetags.core_extras import (
    dicom_job_status_css_class,
    dicom_task_status_css_class,
)


class RecordIdColumn(tables.TemplateColumn):
    def __init__(self, verbose_name):
        template_code = (
            '<a href="{{ record.get_absolute_url }}">'
            "{{ value }} "
            '{% include "core/icons/goto.svg" %}'
            "</a>"
        )
        super().__init__(template_code=template_code, verbose_name=verbose_name)


class DicomJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")

    class Meta:
        model = None
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        # owner is dynamically excluded for non staff users (see tables.py)
        fields = ("id", "status", "source", "created", "owner")
        empty_text = "No jobs to show"
        attrs = {
            "id": "dicom_job_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        css_class = dicom_job_status_css_class(record.status)
        return format_html(f'<span class="{css_class}">{value}</span>')


class TransferJobTable(DicomJobTable):
    class Meta(DicomJobTable.Meta):
        # owner is dynamically excluded for non staff users (see tables.py)
        fields = ("id", "status", "source", "destination", "created", "owner")


class DicomTaskTable(tables.Table):
    task_id = RecordIdColumn(verbose_name="Task ID")
    end = tables.DateTimeColumn(verbose_name="Finished At")

    class Meta:
        model = None
        order_by = ("task_id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("task_id", "status", "message", "end")
        empty_text = "No tasks to show"
        attrs = {"class": "table table-bordered table-hover"}

    def render_status(self, value, record):
        css_class = dicom_task_status_css_class(record.status)
        return format_html(f'<span class="{css_class}">{value}</span>')
