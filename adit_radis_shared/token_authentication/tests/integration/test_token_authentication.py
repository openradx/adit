import pytest
import requests
from playwright.sync_api import Page, expect

from adit_radis_shared.common.utils.auth_utils import add_user_to_group


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_create_and_delete_authentication_token(
    page: Page,
    channels_live_server,
    create_and_login_user,
    token_authentication_group,
):
    user = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, token_authentication_group)

    page.goto(channels_live_server.url + "/token-authentication/")
    page.get_by_label("Description").fill("Just a test token")
    page.get_by_text("Generate Token").click()
    expect(page.locator("#unhashed-token-string")).to_be_visible()
    token = page.locator("#unhashed-token-string").inner_text()

    response = requests.get(
        channels_live_server.url + "/token-authentication/test",
        headers={"Authorization": f"Token {token}"},
    )
    assert response.status_code == 200

    expect(page.locator("table").get_by_text("Just a test token")).to_be_visible()
    page.get_by_label("Delete token").click()
    expect(page.locator("table").get_by_text("Just a test token")).not_to_be_visible()

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
