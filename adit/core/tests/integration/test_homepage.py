import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.integration(transaction=True)
def test_homepage_has_title(live_server, page: Page):
    print(live_server.url)
    page.goto(live_server.url)

    # Expect a title "to contain" a substring.
    expect(page).to_have_title(re.compile("Home"))
