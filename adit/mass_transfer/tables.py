from adit.core.tables import DicomTaskTable, TransferJobTable

from .models import MassTransferJob, MassTransferTask


class MassTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = MassTransferJob


class MassTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = MassTransferTask
