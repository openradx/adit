import io
import time
from multiprocessing import Process
from tempfile import NamedTemporaryFile
from typing import Callable

import nest_asyncio
import pandas as pd
import pytest
from django.conf import settings
from django.core.management import call_command
from faker import Faker
from playwright.sync_api import Locator, Page, Response

from adit.core.factories import (
    DicomServerFactory,
    DicomWebServerFactory,
)
from adit.core.models import DicomServer
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.testing import ChannelsLiveServer

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
def channels_live_server(request):
    server = ChannelsLiveServer()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture
def dicom_worker():
    def start_worker():
        call_command("dicom_worker", "-p", "1")

    p = Process(target=start_worker)
    p.start()
    yield
    p.terminate()


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
def login_user(page: Page):
    def _login_user(server_url: str, username: str, password: str):
        page.goto(server_url + "/accounts/login")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_text("Log in").click()

    return _login_user


# TODO: See if we can make it a yield fixture with name logged_in_user
@pytest.fixture
def create_and_login_user(page: Page, login_user):
    def _create_and_login_user(server_url: str) -> User:
        password = "mysecret"
        user = UserFactory.create(password=password)

        login_user(server_url, user.username, password)

        return user

    return _create_and_login_user


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
