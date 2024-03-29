import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.integration
def test_homepage_has_title(live_server, page: Page):
    page.goto(live_server.url)

    # Expect a title "to contain" a substring.
    expect(page).to_have_title(re.compile("Home"))
