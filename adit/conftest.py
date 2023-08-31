import io
import time
from multiprocessing import Process
from tempfile import NamedTemporaryFile
from typing import Callable, Literal

import nest_asyncio
import pandas as pd
import pytest
from django.conf import settings
from django.core.management import call_command
from faker import Faker
from playwright.sync_api import Locator, Response

from adit.core.factories import (
    DicomNodeInstituteAccessFactory,
    DicomServerFactory,
    DicomWebServerFactory,
)
from adit.core.models import DicomNode, DicomServer
from shared.accounts.factories import InstituteFactory
from shared.accounts.models import Institute, User

# We have to explicitly import conftest from shared here to make those
# fixtures also available in the test of the adit subfolder
from shared.conftest import *  # noqa: F403

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
def poll():
    def _poll(
        locator: Locator,
        func: Callable[[Locator], Response | None] = lambda loc: loc.page.reload(),
        interval: int = 1_500,
        timeout: int = 15_000,
    ):
        start_time = time.time()
        while True:
            try:
                locator.wait_for(timeout=interval)
                return locator
            except Exception as err:
                elapsed_time = (time.time() - start_time) * 1000
                if elapsed_time > timeout:
                    raise err

            func(locator)

    return _poll


@pytest.fixture
def adit_celery_worker():
    def start_worker():
        call_command("celery_worker", "-Q", "test_queue")

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
        df.to_excel(output, index=False, engine="openpyxl")

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


@pytest.fixture
def grant_access():
    def _grant_access(
        user: User,
        dicom_node: DicomNode,
        access_type: Literal["source", "destination"],
        institute: Institute | None = None,
    ) -> None:
        if not institute:
            institute = InstituteFactory.create()
        institute.users.add(user)

        if access_type == "source":
            DicomNodeInstituteAccessFactory.create(
                dicom_node=dicom_node, institute=institute, source=True
            )
        elif access_type == "destination":
            DicomNodeInstituteAccessFactory.create(
                dicom_node=dicom_node, institute=institute, destination=True
            )
        else:
            raise AssertionError(f"Invalid access type: {access_type}")

    return _grant_access
