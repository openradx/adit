from pathlib import Path
import logging
import errno
from typing import Type
import re
import os
from datetime import datetime, date, time
import datetime

from adit.core.errors import RetriableTaskError
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.dicom_utils import adit_dict_to_dicom_json
from ..serializers import DicomWebSerializer

from pydicom.dataset import Dataset
from pydicom import dcmread, Sequence

logger = logging.getLogger(__name__)


class DicomWebApi():
    def __init__(self, connector):
        self.connector = connector

    def qido_find_studies(self, query: dict, limit_results=None) -> list:
        studies_list = self.connector.find_studies(
            query, 
            limit_results=limit_results
        )
        studies = adit_dict_to_dicom_json(studies_list)
        return studies

    def qido_find_series(self, query: dict, limit_results=None) -> list:
        series_list = self.connector.find_series(
            query, 
            limit_results=limit_results
        )
        series = adit_dict_to_dicom_json(series_list)
        return series

    def wado_download_study(
        self, 
        study_uid: str, 
        series_list: str,
        mode: str,
        content_type: str,
        folder_path: str,
        serializer: Type[DicomWebSerializer],
        modifier_callback = None,
    ) -> None:
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            self.wado_download_series(
                study_uid, 
                series_uid,
                mode, 
                content_type, 
                folder_path, 
                serializer, 
                modifier_callback=modifier_callback,
            )

        logger.debug("Successfully downloaded study %s to ADIT.", study_uid)

    def wado_download_series(
        self,
        study_uid: str,
        series_uid: str,
        mode: str,
        content_type: str,
        folder_path: str,
        serializer: Type[DicomWebSerializer],
        modifier_callback=None,
    ) -> str:
        dicom_files_path = Path(folder_path) / "dicom_files"
        self.connector.download_series(
            patient_id="",
            study_uid=study_uid, 
            series_uid=series_uid,
            folder=dicom_files_path,
            modifier_callback=modifier_callback
        )
        for file in os.listdir(dicom_files_path):
            ds = dcmread(dicom_files_path / file)
            serializer.write(ds)
            os.remove(dicom_files_path / file)

