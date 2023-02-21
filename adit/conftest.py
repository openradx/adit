import time
from multiprocessing import Process
from typing import Callable
import pytest
from django.conf import settings
from django.core.management import call_command
from playwright.sync_api import Locator, Page
from adit.accounts.factories import UserFactory
from adit.core.factories import DicomServerFactory
from adit.accounts.models import User
from adit.testing import ChannelsLiveServer
from django.contrib.auth.models import Group
from adit.core.models import DicomNode
from adit.groups.models import Access


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
def user_with_permission(db):
    user = UserFactory()
    batch_transfer_group = Group.objects.get(name="batch_transfer_group")
    user.groups.add(batch_transfer_group)
    return user


@pytest.fixture
def user_with_permission_and_general_access(db):
    user = UserFactory()
    batch_transfer_group = Group.objects.get(name="batch_transfer_group")
    user.groups.add(batch_transfer_group)
    Group.objects.create(name="test_group")
    for node in DicomNode.objects.all():
        Access.objects.create(access_type="src", group=Group.objects.get(name="test_group"), node=node)
        Access.objects.create(access_type="dst", group=Group.objects.get(name="test_group"), node=node)
    user.join_group("test_group")

    return user


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
