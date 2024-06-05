from adit.core.models import DicomTask
from adit.core.processors import TransferTaskProcessor

from .models import (
    UploadSettings,
    UploadTask,
)


class UploadTaskProcessor(TransferTaskProcessor):
    app_name = "Upload"
    dicom_task_class = UploadTask
    app_settings_class = UploadSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, UploadTask)
        super().__init__(dicom_task)
