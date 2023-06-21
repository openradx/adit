from adit.core.tables import DicomTaskTable, TransferJobTable

from .models import ContinuousTransferJob, ContinuousTransferTask


class ContinuousTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = ContinuousTransferJob


class ContinuousTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = ContinuousTransferTask
        empty_text = "No transfer tasks to show"
