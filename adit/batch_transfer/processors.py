from adit.core.processors import ProcessDicomTask
from adit.core.types import DicomLogEntry
from adit.core.utils.transfer_utils import TransferExecutor

from .models import BatchTransferSettings, BatchTransferTask


class ProcessBatchTransferTask(ProcessDicomTask):
    app_name = "Batch Transfer"
    dicom_task_class = BatchTransferTask
    app_settings_class = BatchTransferSettings

    def process_dicom_task(
        self, dicom_task
    ) -> tuple[BatchTransferTask.Status, str, list[DicomLogEntry]]:
        assert isinstance(dicom_task, BatchTransferTask)
        return TransferExecutor(dicom_task).start()
