from adit_server.core.tables import DicomTaskTable, TransferJobTable

from .models import BatchTransferJob, BatchTransferTask


class BatchTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = BatchTransferJob


class BatchTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = BatchTransferTask
        empty_text = "No transfer tasks to show"
