from adit.core.processors import ProcessDicomTask
from adit.core.types import DicomLogEntry
from adit.core.utils.transfer_utils import TransferExecutor

from .models import (
    SelectiveTransferSettings,
    SelectiveTransferTask,
)


class ProcessSelectiveTransferTask(ProcessDicomTask):
    dicom_task_class = SelectiveTransferTask
    app_settings_class = SelectiveTransferSettings

    def handle_dicom_task(
        self, dicom_task
    ) -> tuple[SelectiveTransferTask.Status, str, list[DicomLogEntry]]:
        assert isinstance(dicom_task, SelectiveTransferTask)
        return TransferExecutor(dicom_task, self).start()
