import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import (
    add_permission,
    add_user_to_group,
)
from asgiref.sync import async_to_sync
from django.db import close_old_connections, connections
from django.test.client import AsyncRequestFactory
from rest_framework.exceptions import NotFound

from adit.selective_transfer.utils.testing_helpers import create_selective_transfer_group
from adit.selective_transfer.views import selective_transfer_download_study_view


@pytest.fixture
def arf():
    return AsyncRequestFactory()


def _build_download_request(arf, user, server_id, patient_id, study_uid, query_params=None):
    path = f"/selective-transfer/download/{server_id}/{patient_id}/{study_uid}/"
    request = arf.get(path, query_params or {})
    request.user = user

    async def _auser():
        return user

    request.auser = _auser
    request.session = {}
    return request


@pytest.fixture(autouse=True)
def close_db_connections():
    close_old_connections()  # clear any inherited handles
    try:
        yield
    finally:
        close_old_connections()
        connections.close_all()  # release the connection this test opened


@pytest.fixture
def user_with_download_rights(db):
    user = UserFactory(is_active=True)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, "selective_transfer", "can_download_study")
    return user


@pytest.mark.django_db(transaction=True)
def test_download_with_invalid_server_returns_404(arf, user_with_download_rights, monkeypatch):
    server_id = 123456789
    patient_id = 1001
    study_uid = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"

    request = _build_download_request(
        arf,
        user_with_download_rights,
        server_id=f"{server_id}",
        patient_id=f"{patient_id}",
        study_uid=f"{study_uid}",
        query_params={"study_date": "20240101", "study_time": "010203"},
    )

    class EarlyFailingDownloader:
        def __init__(self, server_id):
            self.server_id = server_id

        def download_study(self, *, user, patient_id, study_uid, study_params, download_folder):
            async def _stream():
                yield b""

            return _stream()

        async def wait_until_ready(self):
            raise NotFound("Invalid DICOM server.")

    monkeypatch.setattr("adit.selective_transfer.views.DicomDownloader", EarlyFailingDownloader)

    response = async_to_sync(selective_transfer_download_study_view)(
        request, server_id=f"{server_id}", patient_id=f"{patient_id}", study_uid=f"{study_uid}"
    )

    assert response.status_code == 404
    assert "Invalid DICOM server." in response.content.decode()
