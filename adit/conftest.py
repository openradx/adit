import time
from typing import Callable
import pytest
from playwright.sync_api import Locator, Page
from adit.accounts.factories import UserFactory
from adit.testing import ChannelsLiveServer


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
def login_user(page: Page):
    def _login_user(server_url: str):
        password = "mysecret"
        user = UserFactory(password=password)

        page.goto(server_url + "/accounts/login")
        page.get_by_label("Username").fill(user.username)
        page.get_by_label("Password").fill(password)
        page.get_by_text("Log in").click()

        return user

    return _login_user
