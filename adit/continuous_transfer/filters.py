from adit.core.filters import TransferJobFilter
from .models import ContinuousTransferJob


class ContinuousTransferJobFilter(TransferJobFilter):
    class Meta(TransferJobFilter.Meta):
        model = ContinuousTransferJob
