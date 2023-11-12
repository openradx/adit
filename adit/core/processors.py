import logging

from .models import AppSettings, DicomTask
from .types import DicomLogEntry

logger = logging.getLogger(__name__)

ProcessingResult = tuple[DicomTask.Status, str, list[DicomLogEntry]]


class ProcessDicomTask:
    app_name: str
    dicom_task_class: type[DicomTask]
    app_settings_class: type[AppSettings]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def is_suspended(self) -> bool:
        app_settings = self.app_settings_class.get()
        assert app_settings
        return app_settings.suspended

    def process_dicom_task(self, dicom_task: DicomTask) -> ProcessingResult:
        """Does the actual work of processing the dicom task.

        Should return a tuple of the final status of that task, a message that is
        stored in the task model and a list of log entries (e.g. warnings).
        """
        raise NotImplementedError("Subclasses must implement this method.")
