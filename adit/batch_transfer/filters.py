from adit.core.filters import DicomJobFilter, DicomTaskFilter
from .models import BatchTransferJob, BatchTransferTask


class BatchTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = BatchTransferJob


class BatchTransferTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = BatchTransferTask
