from http import HTTPStatus
from io import BytesIO

import pydicom
import pytest
from adit_client import AditClient
from adit_radis_shared.common.utils.testing_helpers import ChannelsLiveServer
from requests.exceptions import HTTPError

from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import (
    create_dicom_web_client,
    load_sample_dicoms_metadata,
    setup_dimse_orthancs,
)
from adit.dicom_web.utils.testing_helpers import create_user_with_dicom_web_group_and_token


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_study(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]

    results = orthanc1_client.retrieve_study(study_uid)
    series_uids = set()
    for result in results:
        assert isinstance(result, pydicom.Dataset)
        assert result.StudyInstanceUID == study_uid
        series_uids.add(result.SeriesInstanceUID)
    assert series_uids == set(
        metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_study_with_manipulation(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    test_pseudonym = "TestPseudonym"
    test_protocol_id = "TestProtocolID"
    test_protocol_name = "TestProtocolName"

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(
        server_url=channels_live_server.url,
        auth_token=token,
        trial_protocol_id=test_protocol_id,
        trial_protocol_name=test_protocol_name,
    )

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]

    results = adit_client.retrieve_study(server.ae_title, study_uid, test_pseudonym)
    series_uids = set()
    for result in results:
        assert isinstance(result, pydicom.Dataset)
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym
        assert result.StudyInstanceUID != study_uid
        assert result.ClinicalTrialProtocolID == test_protocol_id
        assert result.ClinicalTrialProtocolName == test_protocol_name
        session_id = f"{result.StudyDate}-{result.StudyTime}"
        assert result.PatientComments == (
            f"Project:{test_protocol_id} Subject:{test_pseudonym} "
            f"Session:{test_pseudonym}_{session_id}"
        )
        series_uids.add(result.SeriesInstanceUID)
    assert series_uids.isdisjoint(
        set(metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"])
    )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_study_with_invalid_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    test_pseudonym = "Test\\Pseudonym1"

    with pytest.raises(HTTPError) as exc_info:
        adit_client.retrieve_study(server.ae_title, study_uid, test_pseudonym)

    response = exc_info.value.response
    assert response is not None
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()
    assert "pseudonym" in error or "invalid" in str(error).lower(), f"Unexpected error: {error}"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_study_metadata(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]

    results = orthanc1_client.retrieve_study_metadata(study_uid)
    series_uids = set()
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(result, "PixelData")
        assert result.StudyInstanceUID == study_uid
        series_uids.add(result.SeriesInstanceUID)
    assert series_uids == set(
        metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_study_metadata_with_manipulation(
    channels_live_server: ChannelsLiveServer,
):
    setup_dimse_orthancs()

    test_pseudonym = "TestPseudonym"
    test_protocol_id = "TestProtocolID"
    test_protocol_name = "TestProtocolName"

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(
        server_url=channels_live_server.url,
        auth_token=token,
        trial_protocol_id=test_protocol_id,
        trial_protocol_name=test_protocol_name,
    )

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]

    results = adit_client.retrieve_study_metadata(server.ae_title, study_uid, test_pseudonym)
    series_uids = set()
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(result, "PixelData")
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym
        assert result.StudyInstanceUID != study_uid
        assert result.ClinicalTrialProtocolID == test_protocol_id
        assert result.ClinicalTrialProtocolName == test_protocol_name
        session_id = f"{result.StudyDate}-{result.StudyTime}"
        assert result.PatientComments == (
            f"Project:{test_protocol_id} Subject:{test_pseudonym} "
            f"Session:{test_pseudonym}_{session_id}"
        )
        series_uids.add(result.SeriesInstanceUID)
    assert series_uids.isdisjoint(
        set(metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"])
    )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_study_metadata_with_invalid_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    test_pseudonym = "Test\\Pseudonym1"

    with pytest.raises(HTTPError) as exc_info:
        adit_client.retrieve_study_metadata(server.ae_title, study_uid, test_pseudonym)

    response = exc_info.value.response
    assert response is not None
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()
    assert "pseudonym" in error or "invalid" in str(error).lower(), f"Unexpected error: {error}"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_series(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    series_uid: str = metadata.iloc[0]["SeriesInstanceUID"]

    results = orthanc1_client.retrieve_series(study_uid, series_uid)
    for result in results:
        assert isinstance(result, pydicom.Dataset)
        assert result.StudyInstanceUID == study_uid
        assert result.SeriesInstanceUID == series_uid


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_series_with_manipulation(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    test_pseudonym = "TestPseudonym"
    test_protocol_id = "TestProtocolID"
    test_protocol_name = "TestProtocolName"

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(
        server_url=channels_live_server.url,
        auth_token=token,
        trial_protocol_id=test_protocol_id,
        trial_protocol_name=test_protocol_name,
    )

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    series_uid: str = metadata.iloc[0]["SeriesInstanceUID"]

    results = adit_client.retrieve_series(server.ae_title, study_uid, series_uid, test_pseudonym)
    for result in results:
        assert isinstance(result, pydicom.Dataset)
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym
        assert result.StudyInstanceUID != study_uid
        assert result.SeriesInstanceUID != series_uid
        assert result.ClinicalTrialProtocolID == test_protocol_id
        assert result.ClinicalTrialProtocolName == test_protocol_name
        session_id = f"{result.StudyDate}-{result.StudyTime}"
        assert result.PatientComments == (
            f"Project:{test_protocol_id} Subject:{test_pseudonym} "
            f"Session:{test_pseudonym}_{session_id}"
        )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_series_with_invalid_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    series_uid: str = metadata.iloc[0]["SeriesInstanceUID"]
    test_pseudonym = "Test\\Pseudonym1"

    with pytest.raises(HTTPError) as exc_info:
        adit_client.retrieve_series(server.ae_title, study_uid, series_uid, test_pseudonym)

    response = exc_info.value.response
    assert response is not None
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()
    assert "pseudonym" in error or "invalid" in str(error).lower(), f"Unexpected error: {error}"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_series_metadata(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]

    results = orthanc1_client.retrieve_series_metadata(study_uid, series_uid)
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(result, "PixelData")
        assert result.StudyInstanceUID == study_uid
        assert result.SeriesInstanceUID == series_uid


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_series_metadata_with_manipulation(
    channels_live_server: ChannelsLiveServer,
):
    setup_dimse_orthancs()

    test_pseudonym = "TestPseudonym"
    test_protocol_id = "TestProtocolID"
    test_protocol_name = "TestProtocolName"

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(
        server_url=channels_live_server.url,
        auth_token=token,
        trial_protocol_id=test_protocol_id,
        trial_protocol_name=test_protocol_name,
    )

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]

    results = adit_client.retrieve_series_metadata(
        server.ae_title, study_uid, series_uid, test_pseudonym
    )
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(result, "PixelData")
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym
        assert result.StudyInstanceUID != study_uid
        assert result.SeriesInstanceUID != series_uid
        assert result.ClinicalTrialProtocolID == test_protocol_id
        assert result.ClinicalTrialProtocolName == test_protocol_name
        session_id = f"{result.StudyDate}-{result.StudyTime}"
        assert result.PatientComments == (
            f"Project:{test_protocol_id} Subject:{test_pseudonym} "
            f"Session:{test_pseudonym}_{session_id}"
        )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_series_metadata_with_invalid_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    test_pseudonym = "Test\\Pseudonym1"

    with pytest.raises(HTTPError) as exc_info:
        adit_client.retrieve_series_metadata(server.ae_title, study_uid, series_uid, test_pseudonym)

    response = exc_info.value.response
    assert response is not None
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()
    assert "pseudonym" in error or "invalid" in str(error).lower(), f"Unexpected error: {error}"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_image(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]

    result = orthanc1_client.retrieve_instance(study_uid, series_uid, image_uid)
    assert isinstance(result, pydicom.Dataset)
    assert result.StudyInstanceUID == study_uid
    assert result.SeriesInstanceUID == series_uid
    assert result.SOPInstanceUID == image_uid


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_image_with_manipulation(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    test_pseudonym = "TestPseudonym"
    test_protocol_id = "TestProtocolID"
    test_protocol_name = "TestProtocolName"

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(
        server_url=channels_live_server.url,
        auth_token=token,
        trial_protocol_id=test_protocol_id,
        trial_protocol_name=test_protocol_name,
    )

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]

    result = adit_client.retrieve_image(
        server.ae_title, study_uid, series_uid, image_uid, test_pseudonym
    )
    assert isinstance(result, pydicom.Dataset)
    assert result.PatientID == test_pseudonym
    assert result.PatientName == test_pseudonym
    assert result.StudyInstanceUID != study_uid
    assert result.SeriesInstanceUID != series_uid
    assert result.SOPInstanceUID != image_uid
    assert result.ClinicalTrialProtocolID == test_protocol_id
    assert result.ClinicalTrialProtocolName == test_protocol_name
    session_id = f"{result.StudyDate}-{result.StudyTime}"
    assert result.PatientComments == (
        f"Project:{test_protocol_id} Subject:{test_pseudonym} Session:{test_pseudonym}_{session_id}"
    )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_image_with_invalid_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]
    test_pseudonym = "Test\\Pseudonym1"

    with pytest.raises(HTTPError) as exc_info:
        adit_client.retrieve_image(
            server.ae_title, study_uid, series_uid, image_uid, test_pseudonym
        )

    response = exc_info.value.response
    assert response is not None
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()
    assert "pseudonym" in error or "invalid" in str(error).lower(), f"Unexpected error: {error}"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_image_metadata(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]

    result = orthanc1_client.retrieve_instance_metadata(study_uid, series_uid, image_uid)
    result = pydicom.Dataset.from_json(result)
    assert not hasattr(result, "PixelData")
    assert result.StudyInstanceUID == study_uid
    assert result.SeriesInstanceUID == series_uid
    assert result.SOPInstanceUID == image_uid


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_image_metadata_with_manipulation(
    channels_live_server: ChannelsLiveServer,
):
    setup_dimse_orthancs()

    test_pseudonym = "TestPseudonym"
    test_protocol_id = "TestProtocolID"
    test_protocol_name = "TestProtocolName"

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(
        server_url=channels_live_server.url,
        auth_token=token,
        trial_protocol_id=test_protocol_id,
        trial_protocol_name=test_protocol_name,
    )

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]
    test_pseudonym = "TestPseudonym"

    result = adit_client.retrieve_image_metadata(
        server.ae_title, study_uid, series_uid, image_uid, test_pseudonym
    )
    result = pydicom.Dataset.from_json(result)
    assert not hasattr(result, "PixelData")
    assert result.PatientID == test_pseudonym
    assert result.PatientName == test_pseudonym
    assert result.StudyInstanceUID != study_uid
    assert result.SeriesInstanceUID != series_uid
    assert result.SOPInstanceUID != image_uid
    assert result.ClinicalTrialProtocolID == test_protocol_id
    assert result.ClinicalTrialProtocolName == test_protocol_name
    session_id = f"{result.StudyDate}-{result.StudyTime}"
    assert result.PatientComments == (
        f"Project:{test_protocol_id} Subject:{test_pseudonym} Session:{test_pseudonym}_{session_id}"
    )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_image_metadata_with_invalid_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]
    test_pseudonym = "Test\\Pseudonym1"

    with pytest.raises(HTTPError) as exc_info:
        adit_client.retrieve_image_metadata(
            server.ae_title, study_uid, series_uid, image_uid, test_pseudonym
        )

    response = exc_info.value.response
    assert response is not None
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()
    assert "pseudonym" in error or "invalid" in str(error).lower(), f"Unexpected error: {error}"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_nifti_study(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]

    # Call the retrieve_nifti_study method
    nifti_files = adit_client.retrieve_nifti_study(server.ae_title, study_uid)

    # Validate the response
    assert len(nifti_files) > 0, "No NIfTI files were returned"
    for filename, file_content in nifti_files:
        assert isinstance(filename, str), f"Filename is not a string: {filename}"
        assert isinstance(file_content, BytesIO), (
            f"File content is not a BytesIO object: {filename}"
        )
        assert file_content.getbuffer().nbytes > 0, f"File {filename} is empty"
        print(f"Debug: NIfTI file {filename} size: {file_content.getbuffer().nbytes} bytes")
