from adit.core.tables import DicomTaskTable, TransferJobTable
from .models import SelectiveTransferJob, SelectiveTransferTask


class SelectiveTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = SelectiveTransferJob


class SelectiveTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = SelectiveTransferTask
