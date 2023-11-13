from adit.core.processors import ProcessDicomTask
from adit.core.types import DicomLogEntry

from .models import BatchQuerySettings, BatchQueryTask
from .utils.query_utils import QueryExecutor


class ProcessBatchQueryTask(ProcessDicomTask):
    app_name = "Batch Query"
    dicom_task_class = BatchQueryTask
    app_settings_class = BatchQuerySettings

    def process_dicom_task(
        self, dicom_task
    ) -> tuple[BatchQueryTask.Status, str, list[DicomLogEntry]]:
        assert isinstance(dicom_task, BatchQueryTask)
        return QueryExecutor(dicom_task).start()
