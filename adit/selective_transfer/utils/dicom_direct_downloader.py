from datetime import datetime

from django.conf import settings

from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator


class DicomDirectDownloader:
    def __init__(self, server: DicomServer):
        timeout = settings.DICOM_EXPLORER_RESPONSE_TIMEOUT
        self.operator = DicomOperator(server, connection_retries=1, dimse_timeout=timeout)

    # adapted from adit.core.processors.py
    def download_study(
        self,
        study_uid: str,
        study_folder: Path,
        modifier: Callable,
    ) -> None:
        def callback(ds: Dataset | None) -> None:
            if ds is None:
                return

            modifier(ds)

            final_folder: Path
            if settings.CREATE_SERIES_SUB_FOLDERS:
                series_folder_name = sanitize_filename(f"{ds.SeriesNumber}-{ds.SeriesDescription}")
                final_folder = study_folder / series_folder_name
            else:
                final_folder = study_folder

            final_folder.mkdir(parents=True, exist_ok=True)
            file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
            file_path = final_folder / file_name
            write_dataset(ds, file_path)

        
        # Without pseudonymization we transfer the whole study as it is.
        self.operator.fetch_study(
            patient_id=patient_id,
            study_uid=study_uid,
            callback=callback,