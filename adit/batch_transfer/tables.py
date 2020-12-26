import django_tables2 as tables
from adit.core.tables import TransferJobTable, BatchTaskTable
from .models import BatchTransferJob, BatchTransferRequest


class BatchTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferJob


class BatchTransferRequestTable(BatchTaskTable):
    transfer_tasks = tables.columns.TemplateColumn(
        verbose_name="Transfer Tasks",
        template_name="batch_transfer/_batch_transfer_tasks_column.html",
    )

    class Meta(BatchTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferRequest
        fields = ("batch_id", "status", "transfer_tasks", "end")
        empty_text = "No requests to show"
