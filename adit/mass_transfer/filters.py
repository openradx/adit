from adit.core.filters import DicomJobFilter, DicomTaskFilter

from .models import MassTransferJob, MassTransferTask


class MassTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = MassTransferJob


class MassTransferTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = MassTransferTask
