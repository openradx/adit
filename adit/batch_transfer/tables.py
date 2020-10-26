import django_tables2 as tables
from .models import BatchTransferRequest


class BatchTransferRequestTable(tables.Table):
    end = tables.Column(verbose_name="Finished at")

    class Meta:  # pylint: disable=too-few-public-methods
        model = BatchTransferRequest
        order_by = ("row_number",)
        template_name = "django_tables2/bootstrap4.html"
        fields = ("row_number", "status", "message", "end")
        attrs = {"id": "requests-table", "class": "table table-bordered table-hover"}
