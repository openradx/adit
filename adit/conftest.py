import pytest
from playwright.sync_api import BrowserContext
from adit.accounts.factories import UserFactory


@pytest.fixture
def page_user(context: BrowserContext, live_server):
    password = "mysecret"
    user = UserFactory(password=password)

    page = context.new_page()
    page.goto(live_server.url + "/accounts/login")
    page.get_by_label("Username").fill(user.username)
    page.get_by_label("Password").fill(password)
    page.get_by_text("Log in").click()

    return page, user
