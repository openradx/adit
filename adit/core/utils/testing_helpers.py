import functools
import io
import os
from typing import Any, Iterable
from unittest.mock import MagicMock, create_autospec

import pandas as pd
from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission
from dicomweb_client import DICOMwebClient
from django.conf import settings
from django.core.management import call_command
from playwright.sync_api import FilePayload
from pydicom import Dataset
from pynetdicom.association import Association
from pynetdicom.status import Status

from adit.core.factories import DicomMoveServerFactory, DicomServerFactory, DicomWebServerFactory
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset

Response = tuple[Dataset, Dataset | None]


class DicomTestHelper:
    @staticmethod
    def create_dataset_from_dict(data: dict[str, Any]) -> Dataset:
        ds = Dataset()
        for i in data:
            setattr(ds, i, data[i])
        return ds

    @staticmethod
    def create_successful_c_find_responses(data_dicts: list[dict[str, Any]]) -> Iterable[Response]:
        responses: list[tuple[Dataset, Dataset | None]] = []
        for data_dict in data_dicts:
            identifier = DicomTestHelper.create_dataset_from_dict(data_dict)
            pending_status = Dataset()
            pending_status.Status = Status.PENDING
            responses.append((pending_status, identifier))

        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        responses.append((success_status, None))

        return iter(responses)

    @staticmethod
    def create_successful_c_get_response() -> Iterable[Response]:
        responses: list[Response] = []
        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        responses.append((success_status, None))
        return iter(responses)

    @staticmethod
    def create_successful_c_move_response() -> Iterable[Response]:
        return DicomTestHelper.create_successful_c_get_response()

    @staticmethod
    def create_successful_c_store_response() -> Dataset:
        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        return success_status


def create_association_mock() -> MagicMock:
    assoc = create_autospec(Association)
    assoc.is_established = True
    return assoc


def create_dicom_operator() -> DicomOperator:
    server = DicomServerFactory.create()
    return DicomOperator(server)


def create_example_transfer_group():
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "example_app", "add_exampletransferjob")
    add_permission(group, "example_app", "view_exampletransferjob")
    return group


def create_resources(transfer_task):
    ds = Dataset()
    ds.PatientID = transfer_task.patient_id
    patient = ResultDataset(ds)

    ds = Dataset()
    ds.PatientID = transfer_task.patient_id
    ds.StudyInstanceUID = transfer_task.study_uid
    ds.StudyDate = "20190923"
    ds.StudyTime = "080000"
    ds.ModalitiesInStudy = ["CT", "SR"]
    study = ResultDataset(ds)

    return patient, study


def setup_dimse_orthancs(cget_enabled: bool = True) -> tuple[DicomServer, DicomServer]:
    call_command("populate_orthancs", reset=True)
    if cget_enabled:
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
    else:
        orthanc1 = DicomMoveServerFactory.create(
            name="Orthanc Test Server 1",
            ae_title="ORTHANC1",
            host=settings.ORTHANC1_HOST,
            port=settings.ORTHANC1_DICOM_PORT,
        )
        orthanc2 = DicomMoveServerFactory.create(
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
    client = DICOMwebClient(
        url=f"{server_url}/api/dicom-web/{ae_title}",
        qido_url_prefix="qidors",
        wado_url_prefix="wadors",
        stow_url_prefix="stowrs",
        headers={"Authorization": f"Token {token_string}"},
    )

    # Force new HTTP connection per request to avoid keep-alive reuse issues during tests
    # This is only a problem with the Django live test server that does not handle keep-alive
    # connections well.
    if getattr(client, "_session", None):
        client._session.headers["Connection"] = "close"

    return client


def load_sample_dicoms(patient_id: str | None = None) -> Iterable[Dataset]:
    test_dicoms_path = settings.BASE_PATH / "samples" / "dicoms"
    if patient_id:
        test_dicoms_path = test_dicoms_path / patient_id

    for root, _, files in os.walk(test_dicoms_path):
        for file in files:
            try:
                ds = read_dataset(os.path.join(root, file))
            except Exception:
                continue
            yield ds


@functools.lru_cache(maxsize=None)
def load_sample_dicoms_metadata(patient_id: str | None = None) -> pd.DataFrame:
    metadata = []
    for ds in load_sample_dicoms(patient_id):
        metadata.append(
            {
                "PatientID": ds.PatientID,
                "StudyInstanceUID": ds.StudyInstanceUID,
                "SeriesInstanceUID": ds.SeriesInstanceUID,
                "SOPInstanceUID": ds.SOPInstanceUID,
                "Modality": ds.Modality,
            }
        )
    return pd.DataFrame(metadata)
