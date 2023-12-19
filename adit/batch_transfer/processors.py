from adit.core.processors import DicomTaskProcessor
from adit.core.types import ProcessingResult
from adit.core.utils.transfer_utils import TransferExecutor

from .models import BatchTransferSettings, BatchTransferTask


class BatchTransferTaskProcessor(DicomTaskProcessor):
    app_name = "Batch Transfer"
    dicom_task_class = BatchTransferTask
    app_settings_class = BatchTransferSettings

    def process_dicom_task(self, dicom_task) -> ProcessingResult:
        assert isinstance(dicom_task, BatchTransferTask)
        return TransferExecutor(dicom_task).start()
