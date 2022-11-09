import pytest
from playwright.sync_api import Page
from adit.accounts.factories import UserFactory
from adit.testing import ChannelsLiveServer


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
