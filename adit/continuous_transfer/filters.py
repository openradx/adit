from adit.core.filters import DicomJobFilter, DicomTaskFilter

from .models import ContinuousTransferJob, ContinuousTransferTask


class ContinuousTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = ContinuousTransferJob


class ContinuousTransferTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = ContinuousTransferTask
