from adit.core.tables import TransferJobTable, BatchTaskTable
from .models import BatchTransferJob, BatchTransferTask


class BatchTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferJob


class BatchTransferTaskTable(BatchTaskTable):
    class Meta(BatchTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferTask
        empty_text = "No transfer tasks to show"
