import pytest
from adit_client.client import AditClient
from adit_client.utils.testing_helpers import create_admin_with_group_and_token
from dicomweb_client import DICOMwebClient
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


# Each retrieve method of AditClient, the DICOMwebClient method it calls and its UIDs
RETRIEVE_METHODS = [
    ("retrieve_study", "retrieve_study", ("1.2",)),
    ("retrieve_study_metadata", "retrieve_study_metadata", ("1.2",)),
    ("iter_study", "iter_study", ("1.2",)),
    ("retrieve_series", "retrieve_series", ("1.2", "1.2.3")),
    ("retrieve_series_metadata", "retrieve_series_metadata", ("1.2", "1.2.3")),
    ("iter_series", "iter_series", ("1.2", "1.2.3")),
    ("retrieve_image", "retrieve_instance", ("1.2", "1.2.3", "1.2.3.4")),
    ("retrieve_image_metadata", "retrieve_instance_metadata", ("1.2", "1.2.3", "1.2.3.4")),
]


@pytest.mark.parametrize(("method", "dicomweb_method", "uids"), RETRIEVE_METHODS)
def test_retrieve_sends_pseudonym_and_trial_protocol(
    mocker: MockerFixture, method: str, dicomweb_method: str, uids: tuple[str, ...]
):
    dicomweb_client = mocker.create_autospec(DICOMwebClient, instance=True)
    getattr(dicomweb_client, dicomweb_method).return_value = []
    client = AditClient(
        "http://localhost", "token", trial_protocol_id="TRIAL1", trial_protocol_name="Trial One"
    )
    mocker.patch.object(client, "_create_dicom_web_client", return_value=dicomweb_client)

    # The iter_* methods are generators that only send the request once consumed.
    list(getattr(client, method)("ORTHANC1", *uids, pseudonym="PSEUDO1"))

    assert getattr(dicomweb_client, dicomweb_method).call_args.kwargs["additional_params"] == {
        "pseudonym": "PSEUDO1",
        "trial_protocol_id": "TRIAL1",
        "trial_protocol_name": "Trial One",
    }


@pytest.mark.parametrize(("method", "dicomweb_method", "uids"), RETRIEVE_METHODS)
def test_retrieve_sends_no_params_when_none_given(
    mocker: MockerFixture, method: str, dicomweb_method: str, uids: tuple[str, ...]
):
    dicomweb_client = mocker.create_autospec(DICOMwebClient, instance=True)
    getattr(dicomweb_client, dicomweb_method).return_value = []
    client = AditClient("http://localhost", "token")
    mocker.patch.object(client, "_create_dicom_web_client", return_value=dicomweb_client)

    list(getattr(client, method)("ORTHANC1", *uids))

    getattr(dicomweb_client, dicomweb_method).assert_called_once()
    call = getattr(dicomweb_client, dicomweb_method).call_args
    assert call.kwargs["additional_params"] == {}
    # The series methods pass the series UID by keyword
    sent_uids = list(call.args)
    if "series_instance_uid" in call.kwargs:
        sent_uids.append(call.kwargs["series_instance_uid"])
    assert tuple(sent_uids) == uids
