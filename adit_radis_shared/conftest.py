import time
from typing import Callable

import pytest
from playwright.sync_api import Locator, Page, Response

from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing import ChannelsLiveServer


@pytest.fixture
def channels_live_server(request):
    server = ChannelsLiveServer()
    request.addfinalizer(server.stop)
    return server


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
