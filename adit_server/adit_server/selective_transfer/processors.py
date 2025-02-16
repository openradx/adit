from adit_server.core.models import DicomTask
from adit_server.core.processors import TransferTaskProcessor

from .models import (
    SelectiveTransferSettings,
    SelectiveTransferTask,
)


class SelectiveTransferTaskProcessor(TransferTaskProcessor):
    app_name = "Selective Transfer"
    dicom_task_class = SelectiveTransferTask
    app_settings_class = SelectiveTransferSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, SelectiveTransferTask)
        super().__init__(dicom_task)
