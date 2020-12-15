from adit.core.tables import TransferJobTable
from .models import ContinuousTransferJob


class ContinuousTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):  # pylint: disable=too-few-public-methods
        model = ContinuousTransferJob
