from adit_server.core.models import DicomTask
from adit_server.core.processors import TransferTaskProcessor

from .models import BatchTransferSettings, BatchTransferTask


class BatchTransferTaskProcessor(TransferTaskProcessor):
    app_name = "Batch Transfer"
    dicom_task_class = BatchTransferTask
    app_settings_class = BatchTransferSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, BatchTransferTask)
        super().__init__(dicom_task)
