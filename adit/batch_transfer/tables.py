from django.utils.html import format_html
import django_tables2 as tables
from .models import BatchTransferRequest


class BatchTransferRequestTable(tables.Table):
    transfer_tasks = tables.columns.TemplateColumn(
        verbose_name="Transfer Tasks",
        template_name="batch_transfer/_transfer_tasks_column.html",
    )
    end = tables.DateTimeColumn(verbose_name="Finished at")

    class Meta:  # pylint: disable=too-few-public-methods
        model = BatchTransferRequest
        order_by = ("row_number",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("row_number", "status", "transfer_tasks", "end")
        attrs = {
            "id": "batch_transfer_request_table",
            "class": "table table-bordered table-hover",
        }

    def render_status(self, value, record):
        text_class = ""
        if record.status == BatchTransferRequest.Status.PENDING:
            text_class = "text-secondary"
        elif record.status == BatchTransferRequest.Status.IN_PROGRESS:
            text_class = "text-info"
        elif record.status == BatchTransferRequest.Status.CANCELED:
            text_class = "text-muted"
        elif record.status == BatchTransferRequest.Status.SUCCESS:
            text_class = "text-success"
        elif record.status == BatchTransferRequest.Status.WARNING:
            text_class = "text-warning"
        elif record.status == BatchTransferRequest.Status.FAILURE:
            text_class = "text-danger"
        return format_html(f'<span class="{text_class}">{value}</span>')
