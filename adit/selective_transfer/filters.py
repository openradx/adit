from adit.core.filters import DicomJobFilter, DicomTaskFilter
from .models import SelectiveTransferJob, SelectiveTransferTask


class SelectiveTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = SelectiveTransferJob


class SelectiveTransferTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = SelectiveTransferTask
