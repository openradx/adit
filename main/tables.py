from django.utils.html import format_html
import django_tables2 as tables
from .models import DicomJob


class JobIdColumn(tables.Column):
    attrs = {"td": {"class": "job-id"}}

    def render(self, record, value):  # pylint: disable=arguments-differ
        url = record.get_absolute_url()
        return format_html(f'<a href="{url}">{value}</a>')


class DicomJobTable(tables.Table):
    id = JobIdColumn()

    class Meta:  # pylint: disable=too-few-public-methods
        model = DicomJob
        order_by = ("-id",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "job_type", "status", "source", "destination", "created_at")
        attrs = {"class": "table table-bordered table-hover"}
