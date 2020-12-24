from adit.core.filters import DicomJobFilter
from .models import ContinuousTransferJob


class ContinuousTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = ContinuousTransferJob
