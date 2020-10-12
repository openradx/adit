from django.utils.html import format_html
import django_tables2 as tables
from .models import TransferJob


class RecordIdColumn(tables.Column):
    attrs = {"td": {"class": "record-id"}}

    def render(self, record, value):  # pylint: disable=arguments-differ
        url = record.get_absolute_url()
        return format_html(f'<a href="{url}">{value}</a>')


class JobTypeColumn(tables.Column):
    def render(self, value):  # pylint: disable=arguments-differ
        return value


class TransferJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")
    job_type = JobTypeColumn()

    class Meta:  # pylint: disable=too-few-public-methods
        model = TransferJob
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "job_type", "status", "source", "destination", "created")
        attrs = {"class": "table table-bordered table-hover"}
