import pytest
from adit_client.client import AditClient
from adit_client.utils.testing_helpers import create_admin_with_group_and_token
from pytest_django.live_server_helper import LiveServer
from pytest_mock import MockerFixture

from adit.core.models import DicomServer


@pytest.mark.django_db
def test_store_study(live_server: LiveServer, mocker: MockerFixture):
    mocker.patch("adit.dicom_web.views.stow_store", return_value=DicomServer(name="ORTHANC1"))
    mocker.patch("adit.dicom_web.views.WebDicomAPIView._get_dicom_server", return_value=[])

    _, _, token = create_admin_with_group_and_token()
    client = AditClient(live_server.url, token)

    result = client.store_images("ORTHANC1", [])
    assert len(result.FailedSOPSequence) == 0
