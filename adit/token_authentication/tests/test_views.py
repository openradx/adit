from urllib.parse import urlencode
import pytest
from django.urls import reverse
from adit.accounts.factories import UserFactory
from adit.accounts.models import Group


@pytest.fixture
def token_data(db):
    return urlencode(
        {
            "expiry_time": 1,
            "client": "Test Client",
        }
    )


@pytest.fixture
def user_without_permission(db):
    return UserFactory()


@pytest.fixture
def user_with_permission(db):
    user = UserFactory()
    token_authentication_group = Group.objects.get(name="token_authentication_group")
    user.groups.add(token_authentication_group)
    return user


def test_generate_token_with_permission(client, token_data, user_with_permission):
    client.force_login(user_with_permission)
    response = client.post(
        reverse("token_authentication_generate_token"),
        token_data,
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 200


def test_generate_token_without_permission(client, token_data, user_without_permission):
    client.force_login(user_without_permission)
    response = client.post(
        reverse("token_authentication_generate_token"),
        token_data,
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 403
