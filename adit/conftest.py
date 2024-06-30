import io
from multiprocessing import Process
from tempfile import NamedTemporaryFile

import nest_asyncio
import pandas as pd
import pytest
from adit_radis_shared.conftest import *  # noqa: F403
from django.conf import settings
from django.core.management import call_command
from faker import Faker

from adit.core.factories import (
    DicomServerFactory,
    DicomWebServerFactory,
)
from adit.core.models import DicomServer

fake = Faker()


def pytest_configure():
    # pytest-asyncio doesn't play well with pytest-playwright as
    # pytest-playwright creates an event loop for the whole test suite and
    # pytest-asyncio can't create an additional one then.
    # nest_syncio works around this this by allowing to create nested loops.
    # https://github.com/pytest-dev/pytest-asyncio/issues/543
    # https://github.com/microsoft/playwright-pytest/issues/167
    nest_asyncio.apply()


@pytest.fixture
def dicom_worker():
    def start_worker():
        call_command("dicom_worker", "-p", "1")

    p = Process(target=start_worker)
    p.start()
    yield
    p.terminate()


@pytest.fixture
def dimse_orthancs() -> tuple[DicomServer, DicomServer]:
    call_command("reset_orthancs")

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


@pytest.fixture
def dicomweb_orthancs() -> tuple[DicomServer, DicomServer]:
    call_command("reset_orthancs")

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


@pytest.fixture
def create_excel_file():
    def _create_excel_file(df: pd.DataFrame):
        output = io.BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")  # type: ignore

        return {
            "name": "batch_file.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": output.getvalue(),
        }

    return _create_excel_file


@pytest.fixture
def create_dummy_file():
    def _create_dummy_file(folder: str | None = None, suffix: str = "", size: int = 1024):
        file = NamedTemporaryFile(dir=folder, suffix=suffix, delete=False)
        file.write(fake.binary(size))
        file.close()

    return _create_dummy_file
