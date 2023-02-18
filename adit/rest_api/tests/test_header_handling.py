import pytest
from django.urls import reverse


def test_invalid_authentication_header(client, token, dicom_server):
    response = client.get(
        reverse("qido_rs-studies", kwargs={"pacs": dicom_server}),
        headers={"nonvalid": f"Token {token}"},
    )
    assert response.status_code == 401

    response = client.get(
        reverse("qido_rs-studies", kwargs={"pacs": dicom_server}),
        headers={"Authorization": f"nonvalid {token}"},
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_invalid_authentication_token(client, dicom_server):
    response = client.get(
        reverse("qido_rs-studies", kwargs={"pacs": dicom_server}),
        headers={"nonvalid": "Token nonvalid"},
    )
    assert response.status_code == 401


def test_invalid_dicom_server(client, token, dicom_server):
    response = client.get(
        reverse("qido_rs-studies", kwargs={"pacs": "invalid_dicom_server"}),
        headers={
            "Authorization": f"Token {token}",
        },
    )
    print(response.data)
    assert response.status_code == 400


def test_invalid_accept_header(client, token, dicom_server):
    response = client.get(
        reverse("wado_rs-studies", kwargs={"pacs": dicom_server}),
        headers={
            "Authorization": f"Token {token}",
            "Accept": "multipart/invalid; type=application/dicom; boundary=test_boundary",
        },
    )
    assert response.status_code == 406

    response = client.get(
        reverse("wado_rs-studies", kwargs={"pacs": dicom_server}),
        headers={
            "Authorization": f"Token {token}",
            "Accept": "multipart/related; type=application/invalid; boundary=test_boundary",
        },
    )
    assert response.status_code == 406
