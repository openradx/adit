import io
import os
from typing import Iterable

import pandas as pd
from dicomweb_client import DICOMwebClient
from django.conf import settings
from django.core.management import call_command
from faker import Faker
from playwright.sync_api import FilePayload
from pydicom import Dataset

from adit.core.factories import (
    DicomServerFactory,
    DicomWebServerFactory,
)
from adit.core.models import DicomServer
from adit.core.utils.dicom_utils import read_dataset

fake = Faker()


def setup_dimse_orthancs() -> tuple[DicomServer, DicomServer]:
    call_command("populate_orthancs", reset=True)

    orthanc1 = DicomServerFactory.create(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        host=settings.ORTHANC1_HOST,
        port=settings.ORTHANC1_DICOM_PORT,
    )
    orthanc2 = DicomServerFactory.create(
        name="Orthanc Test Server 2",
        ae_title="ORTHANC2",
        host=settings.ORTHANC2_HOST,
        port=settings.ORTHANC2_DICOM_PORT,
    )

    return orthanc1, orthanc2


def setup_dicomweb_orthancs() -> tuple[DicomServer, DicomServer]:
    call_command("populate_orthancs", reset=True)

    orthanc1 = DicomWebServerFactory.create(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        dicomweb_root_url=f"http://{settings.ORTHANC1_HOST}:{settings.ORTHANC1_HTTP_PORT}/{settings.ORTHANC1_DICOMWEB_ROOT}/",
    )
    orthanc2 = DicomWebServerFactory.create(
        name="Orthanc Test Server 2",
        ae_title="ORTHANC2",
        dicomweb_root_url=f"http://{settings.ORTHANC2_HOST}:{settings.ORTHANC2_HTTP_PORT}/{settings.ORTHANC2_DICOMWEB_ROOT}/",
    )

    return orthanc1, orthanc2


def create_excel_file(df: pd.DataFrame, filename: str) -> FilePayload:
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")  # type: ignore

    return {
        "name": filename,
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "buffer": output.getvalue(),
    }


def create_dicom_web_client(server_url: str, ae_title: str, token_string: str) -> DICOMwebClient:
    return DICOMwebClient(
        url=f"{server_url}/api/dicom-web/{ae_title}",
        qido_url_prefix="qidors",
        wado_url_prefix="wadors",
        stow_url_prefix="stowrs",
        headers={"Authorization": f"Token {token_string}"},
    )


def get_full_data_sheet():
    full_data_sheet_path = settings.BASE_DIR / "samples" / "full_data_sheet.xlsx"
    return pd.read_excel(full_data_sheet_path)


def get_extended_data_sheet():
    extended_data_sheet_path = settings.BASE_DIR / "samples" / "extended_data_sheet.xlsx"
    return pd.read_excel(extended_data_sheet_path)


def load_test_dicoms(patient_id: str) -> Iterable[Dataset]:
    test_dicoms_path = settings.BASE_DIR / "samples" / "dicoms" / patient_id
    for root, _, files in os.walk(test_dicoms_path):
        if len(files) != 0:
            for file in files:
                try:
                    ds = read_dataset(os.path.join(root, file))
                except Exception:
                    continue
                yield ds
