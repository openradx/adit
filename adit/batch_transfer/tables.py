from adit.core.tables import TransferJobTable, DicomTaskTable
from .models import BatchTransferJob, BatchTransferTask


class BatchTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferJob


class BatchTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = BatchTransferTask
        empty_text = "No transfer tasks to show"
