from adit.core.filters import TransferJobFilter
from .models import SelectiveTransferJob


class SelectiveTransferJobFilter(TransferJobFilter):
    class Meta(TransferJobFilter.Meta):
        model = SelectiveTransferJob
