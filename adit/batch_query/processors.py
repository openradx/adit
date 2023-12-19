from adit.core.processors import DicomTaskProcessor
from adit.core.types import ProcessingResult

from .models import BatchQuerySettings, BatchQueryTask
from .utils.query_utils import QueryExecutor


class BatchQueryTaskProcessor(DicomTaskProcessor):
    app_name = "Batch Query"
    dicom_task_class = BatchQueryTask
    app_settings_class = BatchQuerySettings

    def process_dicom_task(self, dicom_task) -> ProcessingResult:
        assert isinstance(dicom_task, BatchQueryTask)
        return QueryExecutor(dicom_task).start()
