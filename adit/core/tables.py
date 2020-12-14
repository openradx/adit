from django.utils.html import format_html
import django_tables2 as tables
from .templatetags.core_extras import (
    transfer_job_status_css_class,
    transfer_task_status_css_class,
)


class RecordIdColumn(tables.Column):
    attrs = {"td": {"class": "record-id"}}

    def render(self, record, value):  # pylint: disable=arguments-differ
        url = record.get_absolute_url()
        return format_html(f'<a href="{url}">{value}</a>')


class TransferJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")

    class Meta:  # pylint: disable=too-few-public-methods
        model = None
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "status", "source", "destination", "created")
        attrs = {
            "id": "transfer_job_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        css_class = transfer_job_status_css_class(record.status)
        return format_html(f'<span class="{css_class}">{value}</span>')


class TransferTaskTable(tables.Table):
    id = RecordIdColumn(verbose_name="Task ID")
    end = tables.DateTimeColumn(verbose_name="Finished At")

    class Meta:  # pylint: disable=too-few-public-methods
        model = None
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "status", "message", "end")
        attrs = {
            "id": "transfer_task_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        css_class = transfer_task_status_css_class(record.status)
        return format_html(f'<span class="{css_class}">{value}</span>')
