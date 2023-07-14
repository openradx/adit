import time

import pytest
import requests
from playwright.sync_api import Page, expect


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_create_and_delete_authentication_token(
    page: Page,
    channels_live_server,
    create_and_login_user,
):
    user = create_and_login_user(channels_live_server.url)
    user.join_group("token_authentication_group")
    page.goto(channels_live_server.url + "/token-authentication/")

    page.get_by_label("Client").fill("test_client")
    page.get_by_text("Generate new token").click()
    page.reload()
    expect(page.locator('[id*="token-str"]')).to_be_visible()
    token = page.query_selector('[id*="token-str"]')
    token_str = token.get_attribute("id").split("-")[-1]  # type: ignore

    response = requests.get(
        channels_live_server.url + "/token-authentication/test",
        headers={"Authorization": f"Token {token_str}"},
    )
    assert response.status_code == 200

    page.on("dialog", lambda dialog: dialog.accept())
    page.query_selector('[id*="delete-token-button"]').click()  # type: ignore
    page.reload()
    time.sleep(5)
    response = requests.get(
        channels_live_server.url + "/token-authentication/test",
        headers={"Authorization": f"Token {token_str}"},
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
