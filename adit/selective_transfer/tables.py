from adit.core.tables import TransferJobTable, TransferTaskTable
from .models import SelectiveTransferJob, SelectiveTransferTask


class SelectiveTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = SelectiveTransferJob


class SelectiveTransferTaskTable(TransferTaskTable):
    class Meta(TransferTaskTable.Meta):  # pylint: disable=too-few-public-methods
        model = SelectiveTransferTask
