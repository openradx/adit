from adit.core.tables import TransferJobTable
from .models import SelectiveTransferJob


class SelectiveTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = SelectiveTransferJob
