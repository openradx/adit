import re
import pytest
from django.conf import settings
from playwright.sync_api import Page, expect


@pytest.mark.integration
@pytest.mark.skipif(not settings.ADIT_FULLSTACK, reason="Needs full webstack.")
def test_homepage_has_title(live_server, page: Page):
    page.goto(live_server.url)

    # Expect a title "to contain" a substring.
    expect(page).to_have_title(re.compile("ADIT"))
