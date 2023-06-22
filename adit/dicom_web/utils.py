import datetime
import errno
import logging
import os
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Dict, List

from pydicom import Sequence, dcmread
from pydicom.dataset import Dataset

from adit.core.errors import RetriableTaskError
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.dicom_utils import adit_dict_to_dicom_json

logger = logging.getLogger(__name__)


class DicomWebApi:
    def __init__(self, connector):
        self.connector = connector

    def qido_find_studies(self, query: dict, limit_results=None) -> list:
        studies_list = self.connector.find_studies(query, limit_results=limit_results)
        studies = adit_dict_to_dicom_json(studies_list)
        return studies

    def qido_find_series(self, query: dict, limit_results=None) -> list:
        series_list = self.connector.find_series(query, limit_results=limit_results)
        series = adit_dict_to_dicom_json(series_list)
        return series

    def wado_download_study(
        self,
        study_uid: str,
        series_list: List[Dict],
        folder_path: str,
        modifier=None,
    ) -> None:
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            self.wado_download_series(
                study_uid,
                series_uid,
                folder_path,
                modifier=modifier,
            )

        logger.debug("Successfully downloaded study %s to ADIT.", study_uid)

    def wado_download_series(
        self,
        study_uid: str,
        series_uid: str,
        folder_path: str,
        modifier=None,
    ) -> None:
        self.connector.download_series(
            patient_id="",
            study_uid=study_uid,
            series_uid=series_uid,
            dest_folder=folder_path,
            modifier=modifier,
        )
