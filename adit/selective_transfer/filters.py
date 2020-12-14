from adit.core.filters import TransferJobFilter, TransferTaskFilter
from .models import SelectiveTransferJob, SelectiveTransferTask


class SelectiveTransferJobFilter(TransferJobFilter):
    class Meta(TransferJobFilter.Meta):
        model = SelectiveTransferJob


class SelectiveTransferTaskFilter(TransferTaskFilter):
    class Meta(TransferTaskFilter.Meta):
        model = SelectiveTransferTask
