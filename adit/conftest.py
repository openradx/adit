import csv
import io
import time
from multiprocessing import Process
from tempfile import NamedTemporaryFile
from typing import Callable

import pytest
from django.conf import settings
from django.core.management import call_command
from faker import Faker
from playwright.sync_api import Locator, Page

from adit.accounts.factories import UserFactory
from adit.core.factories import DicomServerFactory
from adit.testing import ChannelsLiveServer

fake = Faker()


def poll(
    self: Locator,
    func: Callable[[Locator], None] = lambda loc: loc.page.reload(),
    interval: int = 1_000,
    timeout: int = 10_000,
):
    start_time = time.time()
    while True:
        try:
            self.wait_for(timeout=interval)
            return self
        except Exception as err:
            elapsed_time = (time.time() - start_time) * 1000
            if elapsed_time > timeout:
                raise err

        func(self)


Locator.poll = poll


@pytest.fixture
def channels_liver_server(request):
    server = ChannelsLiveServer()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture
def adit_celery_worker():
    def start_worker():
        call_command("celery_worker", "-Q", "test_queue")

    p = Process(target=start_worker)
    p.start()
    yield
    p.terminate()


@pytest.fixture
def setup_orthancs():
    call_command("reset_orthancs")

    DicomServerFactory(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        host=settings.ORTHANC1_HOST,
        port=settings.ORTHANC1_DICOM_PORT,
    )
    DicomServerFactory(
        name="Orthanc Test Server 2",
        ae_title="ORTHANC2",
        host=settings.ORTHANC2_HOST,
        port=settings.ORTHANC2_DICOM_PORT,
    )


@pytest.fixture
def login_user(page: Page):
    def _login_user(server_url: str, username: str, password: str):
        page.goto(server_url + "/accounts/login")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_text("Log in").click()

    return _login_user


@pytest.fixture
def create_and_login_user(page: Page, login_user):
    def _create_and_login_user(server_url: str):
        password = "mysecret"
        user = UserFactory(password=password)

        login_user(server_url, user.username, password)

        return user

    return _create_and_login_user


@pytest.fixture
def create_csv_file():
    def _create_csv_file(data: list[list[str]]):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=settings.CSV_DELIMITER)
        for row in data:
            writer.writerow(row)

        return {
            "name": "batch_file.csv",
            "mimeType": "text/plain",
            "buffer": output.getvalue().encode("utf-8"),
        }

    return _create_csv_file


@pytest.fixture
def create_dummy_file():
    def _create_dummy_file(folder: str | None = None, suffix: str = "", size: int = 1024):
        file = NamedTemporaryFile(dir=folder, suffix=suffix, delete=False)
        file.write(fake.binary(size))
        file.close()

    return _create_dummy_file
