from functools import partial

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import (
    add_permission,
    add_user_to_group,
)
from asgiref.sync import async_to_sync
from django.db import close_old_connections, connections
from django.test.client import AsyncRequestFactory
from pydicom import Dataset
from pytest_mock import MockerFixture
from rest_framework.exceptions import NotFound

from adit.core.factories import DicomServerFactory
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_dataset import ResultDataset
from adit.selective_transfer.utils.dicom_downloader import DicomDownloader
from adit.selective_transfer.utils.testing_helpers import create_selective_transfer_group
from adit.selective_transfer.views import selective_transfer_download_study_view


def _series(series_uid: str, modality: str) -> ResultDataset:
    ds = Dataset()
    ds.SeriesInstanceUID = series_uid
    ds.SeriesNumber = 1
    ds.Modality = modality
    return ResultDataset(ds)


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


@pytest.mark.django_db(transaction=True)
def test_fetch_put_study_excludes_modalities_when_pseudonymizing(
    user_with_download_rights, mocker: MockerFixture
):
    # When pseudonymizing, the downloader transfers on the series level and must
    # skip modalities in settings.EXCLUDE_MODALITIES (PR,SR in the test env), so an
    # SR series is never fetched while the CT series is.
    user = user_with_download_rights
    server = DicomServerFactory.create()
    grant_access(user.active_group, server, source=True)

    operator_mock = mocker.patch(
        "adit.selective_transfer.utils.dicom_downloader.DicomOperator"
    ).return_value
    operator_mock.find_series.return_value = iter(
        [_series("1.2.840.1", "CT"), _series("1.2.840.2", "SR")]
    )

    downloader = DicomDownloader(server_id=str(server.pk))
    # The loop is only touched inside the per-image callback, which never runs
    # here because the operator (and thus fetch_series) is mocked. A mock loop
    # avoids creating/closing a real event loop and polluting global asyncio state.
    downloader._fetch_put_study(
        user=user,
        patient_id="1001",
        study_uid="1.2.3",
        pseudonymize=True,
        modifier=partial(lambda ds: None),
        loop=mocker.MagicMock(),
    )

    fetched_series = [call.args[2] for call in operator_mock.fetch_series.call_args_list]
    assert fetched_series == ["1.2.840.1"]
    operator_mock.fetch_study.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_fetch_put_study_rechecks_access_and_raises_not_found(
    user_with_download_rights, mocker: MockerFixture
):
    # The download re-checks server access at fetch time. A server the user's active
    # group cannot access as a source must yield NotFound and never touch the PACS.
    user = user_with_download_rights
    server = DicomServerFactory.create()  # not granted -> inaccessible

    operator_cls = mocker.patch(
        "adit.selective_transfer.utils.dicom_downloader.DicomOperator"
    )

    downloader = DicomDownloader(server_id=str(server.pk))
    with pytest.raises(NotFound, match=r"Invalid DICOM server\."):
        downloader._fetch_put_study(
            user=user,
            patient_id="1001",
            study_uid="1.2.3",
            pseudonymize=False,
            modifier=partial(lambda ds: None),
            loop=mocker.MagicMock(),
        )

    # No operator/PACS interaction may happen for an inaccessible server.
    operator_cls.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_fetch_put_study_fetches_whole_study_without_pseudonym(
    user_with_download_rights, mocker: MockerFixture
):
    # Without pseudonymization the whole study is fetched in one go (no per-series
    # modality filtering).
    user = user_with_download_rights
    server = DicomServerFactory.create()
    grant_access(user.active_group, server, source=True)

    operator_mock = mocker.patch(
        "adit.selective_transfer.utils.dicom_downloader.DicomOperator"
    ).return_value

    downloader = DicomDownloader(server_id=str(server.pk))
    downloader._fetch_put_study(
        user=user,
        patient_id="1001",
        study_uid="1.2.3",
        pseudonymize=False,
        modifier=partial(lambda ds: None),
        loop=mocker.MagicMock(),
    )

    operator_mock.fetch_study.assert_called_once()
    operator_mock.find_series.assert_not_called()
    operator_mock.fetch_series.assert_not_called()
