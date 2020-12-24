from adit.core.tables import TransferJobTable, DicomTaskTable
from .models import SelectiveTransferJob, SelectiveTransferTask


class SelectiveTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = SelectiveTransferJob


class SelectiveTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = SelectiveTransferTask
