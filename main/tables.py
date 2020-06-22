from django.utils.html import format_html
import django_tables2 as tables
from .models import DicomJob


class JobIdColumn(tables.Column):
    def __init__(self):
        super().__init__()

    def render(self, record, value):
        url = record.get_absolute_url()
        return format_html(f'<a href="{url}">{value}</a>')
        

class DicomJobTable(tables.Table):
    id = JobIdColumn()

    class Meta:
        model = DicomJob
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('id', 'job_type', 'status', 'source', 'destination', 'created_at')