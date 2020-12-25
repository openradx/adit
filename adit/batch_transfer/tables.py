import django_tables2 as tables
from adit.core.tables import TransferJobTable, DicomTaskTable
from .models import BatchTransferJob, BatchTransferRequest


class BatchTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferJob


class BatchTransferRequestTable(DicomTaskTable):
    id = None  # We don't use the id of the request object itself

    transfer_tasks = tables.columns.TemplateColumn(
        verbose_name="Transfer Tasks",
        template_name="batch_transfer/_batch_transfer_tasks_column.html",
    )

    class Meta(DicomTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferRequest
        order_by = ("row_id",)
        fields = ("row_id", "status", "transfer_tasks", "end")
        empty_text = "No requests to show"
