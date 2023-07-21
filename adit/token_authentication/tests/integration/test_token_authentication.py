from typing import Callable

import pytest
import requests
from playwright.sync_api import Locator, Page, expect


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_create_and_delete_authentication_token(
    page: Page,
    poll: Callable[[Locator], Locator],
    channels_live_server,
    create_and_login_user,
):
    user = create_and_login_user(channels_live_server.url)
    user.join_group("token_authentication_group")
    page.goto(channels_live_server.url + "/token-authentication/")

    page.get_by_label("Client").fill("test_client")
    page.get_by_text("Generate Token").click()
    expect(poll(page.locator("#unhashed-token-string"))).to_be_visible()
    token = page.query_selector("#unhashed-token-string").inner_text()  # type: ignore

    response = requests.get(
        channels_live_server.url + "/token-authentication/test",
        headers={"Authorization": f"Token {token}"},
    )
    assert response.status_code == 200

    page.on("dialog", lambda dialog: dialog.accept())
    expect(poll(page.locator("#delete-token-button-test_client"))).to_be_visible()
    page.query_selector("#delete-token-button-test_client").click()  # type: ignore
    expect(page.locator("#table-row-test_client")).not_to_be_visible()
    response = requests.get(
        channels_live_server.url + "/token-authentication/test",
        headers={"Authorization": f"Token {token}"},
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_invalid_authentication_token(
    channels_live_server,
):
    response = requests.get(
        channels_live_server.url + "/token-authentication/test",
        headers={"Authorization": "Token invalid_token"},
    )
    assert response.status_code == 401
