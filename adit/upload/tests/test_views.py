import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_user_must_have_permission_to_access_view(client: Client):
    user = UserFactory.create()
    client.force_login(user)
    response = client.get(reverse("upload_create"))
    assert response.status_code == 403
    # response = client.post(reverse("data_upload", kwargs={"node_id": 1}))
    # assert response.status_code == 403


@pytest.mark.django_db
def test_user_must_be_logged_in_to_access_view(client: Client):
    response = client.get(reverse("upload_create"))
    assert response.status_code == 302
    # response = client.post(reverse("data_upload", kwargs={"node_id": 1}))
    # assert response.status_code == 302
