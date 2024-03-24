import django_tables2 as tables
from django.utils.html import format_html

from .models import DicomJob, DicomTask
from .templatetags.core_extras import (
    dicom_job_status_css_class,
    dicom_task_status_css_class,
)


class RecordIdColumn(tables.TemplateColumn):
    def __init__(self, verbose_name):
        template_code = (
            "{% load bootstrap_icon from common_extras %}"
            '<a href="{{ record.get_absolute_url }}">'
            "{{ value }} "
            '{% bootstrap_icon "box-arrow-in-down-right" %}'
            "</a>"
        )
        super().__init__(template_code=template_code, verbose_name=verbose_name)


class DicomJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")
    created = tables.Column(verbose_name="Created At")

    class Meta:
        model: type[DicomJob]
        order_by = ("-id",)
        # owner is dynamically excluded for non staff users (see views.py)
        fields = ("id", "status", "message", "created", "owner")
        empty_text = "No jobs to show"
        attrs = {
            "id": "dicom_job_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        css_class = dicom_job_status_css_class(record.status)
        return format_html(f'<span class="{css_class} text-nowrap">{value}</span>')


class TransferJobTable(DicomJobTable):
    pass


class DicomTaskTable(tables.Table):
    id = RecordIdColumn(verbose_name="Task ID")
    end = tables.DateTimeColumn(verbose_name="Finished At")

    class Meta:
        model: type[DicomTask]
        order_by = ("id",)
        fields = ("id", "status", "message", "end")
        empty_text = "No tasks to show"
        attrs = {"class": "table table-bordered table-hover"}

    def render_status(self, value, record):
        css_class = dicom_task_status_css_class(record.status)
        return format_html(f'<span class="{css_class} text-nowrap">{value}</span>')
