from adit.core.models import DicomTask
from adit.core.processors import TransferTaskProcessor

from .models import (
    UploadSettings,
    UploadTask,
)


class SelectiveTransferTaskProcessor(TransferTaskProcessor):
    app_name = "Selective Transfer"
    dicom_task_class = UploadTask
    app_settings_class = UploadSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, UploadTask)
        super().__init__(dicom_task)
