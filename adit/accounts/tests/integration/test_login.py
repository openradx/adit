import pytest
from django.conf import settings
from playwright.sync_api import expect


@pytest.mark.integration
@pytest.mark.skipif(not settings.ADIT_FULLSTACK, reason="Needs full webstack.")
def test_login(page_user, live_server):
    page, user = page_user

    expect(page.locator("#navbarDropdown")).to_have_text(user.username)
