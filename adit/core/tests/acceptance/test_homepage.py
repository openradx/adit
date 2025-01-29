import re

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_homepage_has_title(live_server: LiveServer, page: Page):
    page.goto(live_server.url)

    # Expect a title "to contain" a substring.
    expect(page).to_have_title(re.compile("Home"))
