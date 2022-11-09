import pytest
from playwright.sync_api import Page, expect


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_login(page: Page, live_server, login_user):
    user = login_user(live_server.url)

    expect(page.locator("#navbarDropdown")).to_have_text(user.username)
