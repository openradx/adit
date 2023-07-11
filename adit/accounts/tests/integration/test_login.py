import pytest
from playwright.sync_api import Page, expect


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_login(page: Page, live_server, create_and_login_user):
    user = create_and_login_user(live_server.url)
    expect(page.get_by_text(user.username)).to_be_visible()
