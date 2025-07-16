import os
import shutil
import tempfile
from http import HTTPStatus
from io import BytesIO
from pathlib import Path

import pydicom
import pytest
from adit_client import AditClient
from adit_radis_shared.common.utils.testing_helpers import ChannelsLiveServer
from requests.exceptions import HTTPError

from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_to_nifti_converter import DicomToNiftiConverter
from adit.core.utils.testing_helpers import (
    create_dicom_web_client,
    load_sample_dicoms_metadata,
    setup_dimse_orthancs,
)
from adit.dicom_web.utils.testing_helpers import create_user_with_dicom_web_group_and_token


# Get sample data path from environment variable or use a relative path as fallback
def get_sample_dicom_path(patient_id=None):
    """
    Get the path to the sample DICOM files.

    Args:
        patient_id: Optional patient ID to append to the path

    Returns:
        Path object pointing to the sample DICOM directory
    """
    # First try environment variable
    sample_base_dir = os.environ.get("SAMPLE_DICOM_DIR")

    if not sample_base_dir:
        # If env var not set, try common locations
        for path in [
            # Standard location in container
            "/app/samples/dicoms",
            # Relative to project root
            str(Path(__file__).resolve().parents[5] / "samples" / "dicoms"),
        ]:
            if Path(path).exists():
                sample_base_dir = path
                break

    if not sample_base_dir:
        raise ValueError(
            (
                "Could not locate sample DICOM directory. "
                "Please set SAMPLE_DICOM_DIR environment variable."
            )
        )

    base_path = Path(sample_base_dir)

    if patient_id:
        return base_path / str(patient_id)
    return base_path


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

    nifti_files = adit_client.retrieve_nifti_study(server.ae_title, study_uid)

    assert len(nifti_files) > 0, "No NIfTI files were returned"

    # Normalize filenames returned by retrieve_nifti_study
    nifti_files_dict = {filename: file_content for filename, file_content in nifti_files}
    
    # Check for both .nii.gz and .json files
    nii_files = [f for f in nifti_files_dict.keys() if f.endswith('.nii.gz')]
    json_files = [f for f in nifti_files_dict.keys() if f.endswith('.json')]
    
    assert len(nii_files) > 0, "No .nii.gz files were returned"
    assert len(json_files) > 0, "No .json files were returned"

    # Use DicomToNiftiConverter to convert DICOM files to NIfTI
    sample_dicom_folder = get_sample_dicom_path("1001")
    with tempfile.TemporaryDirectory() as temp_output_folder:
        temp_output_path = Path(temp_output_folder)

        converter = DicomToNiftiConverter()
        converter.convert(dicom_folder=sample_dicom_folder, output_folder=temp_output_path)

        converted_nii_files = list(temp_output_path.glob("*.nii.gz"))
        converted_json_files = list(temp_output_path.glob("*.json"))
        
        assert len(converted_nii_files) > 0, "No NIfTI files were generated by DicomToNiftiConverter"
        assert len(converted_json_files) > 0, "No JSON files were generated by DicomToNiftiConverter"

        # Compare filenames and contents for .nii.gz files
        for converted_file in converted_nii_files:
            # Check if the filename exists in the retrieved files
            assert converted_file.name in nifti_files_dict, (
                f"Filename {converted_file.name} not found in retrieved files"
            )

            file_content = nifti_files_dict[converted_file.name]

            # Check file contents
            assert isinstance(file_content, BytesIO), (
                f"File content is not a BytesIO object: {converted_file.name}"
            )
            assert converted_file.stat().st_size > 0, (
                f"Converted file {converted_file.name} is empty"
            )
            with open(converted_file, "rb") as f:
                converted_content = f.read()
            assert file_content.getvalue() == converted_content, (
                f"Content mismatch for file {converted_file.name}"
            )
            
        # Compare filenames and contents for .json files
        for converted_file in converted_json_files:
            # Check if the filename exists in the retrieved files
            assert converted_file.name in nifti_files_dict, (
                f"Filename {converted_file.name} not found in retrieved files"
            )

            file_content = nifti_files_dict[converted_file.name]

            # Check file contents
            assert isinstance(file_content, BytesIO), (
                f"File content is not a BytesIO object: {converted_file.name}"
            )
            assert converted_file.stat().st_size > 0, (
                f"Converted file {converted_file.name} is empty"
            )
            with open(converted_file, "rb") as f:
                converted_content = f.read()
            assert file_content.getvalue() == converted_content, (
                f"Content mismatch for file {converted_file.name}"
            )
@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_nifti_series(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()

    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)

    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    series_uid: str = metadata.iloc[0]["SeriesInstanceUID"]

    nifti_files = adit_client.retrieve_nifti_series(server.ae_title, study_uid, series_uid)

    assert len(nifti_files) > 0, "No NIfTI files were returned"

    # Normalize filenames returned by retrieve_nifti_series
    nifti_files_dict = {filename: file_content for filename, file_content in nifti_files}
    
    # Check for both .nii.gz and .json files
    nii_files = [f for f in nifti_files_dict.keys() if f.endswith('.nii.gz')]
    json_files = [f for f in nifti_files_dict.keys() if f.endswith('.json')]
    
    assert len(nii_files) > 0, "No .nii.gz files were returned"
    assert len(json_files) > 0, "No .json files were returned"
    
    # Use DicomToNiftiConverter to convert DICOM files to NIfTI
    sample_dicom_folder = get_sample_dicom_path("1001")
    with tempfile.TemporaryDirectory() as temp_output_folder:
        temp_output_path = Path(temp_output_folder)

        # Create a filtered folder with only the specific series
        filtered_folder = temp_output_path / "filtered"
        filtered_folder.mkdir()

        # Filter DICOM files by series UID
        series_files = []
        for root, _, files in os.walk(sample_dicom_folder):
            for file in files:
                if not file.endswith(".dcm"):
                    continue
                file_path = Path(root) / file
                try:
                    ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                    if hasattr(ds, "SeriesInstanceUID") and ds.SeriesInstanceUID == series_uid:
                        series_files.append(file_path)
                        shutil.copy(file_path, filtered_folder / file)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        # Filter DICOM files by series UID
        assert len(series_files) > 0, f"No DICOM files found for series UID {series_uid}"

        converter = DicomToNiftiConverter()
        converter.convert(dicom_folder=filtered_folder, output_folder=temp_output_path)

        converted_nii_files = list(temp_output_path.glob("*.nii.gz"))
        converted_json_files = list(temp_output_path.glob("*.json"))
        
        assert len(converted_nii_files) > 0, "No NIfTI files were generated by DicomToNiftiConverter"
        assert len(converted_json_files) > 0, "No JSON files were generated by DicomToNiftiConverter"

        # Compare filenames and contents for .nii.gz files
        for converted_file in converted_nii_files:
            # Check if the filename exists in the retrieved files
            assert converted_file.name in nifti_files_dict, (
                f"Filename {converted_file.name} not found in retrieved files"
            )

            file_content = nifti_files_dict[converted_file.name]

            # Check file contents
            assert isinstance(file_content, BytesIO), (
                f"File content is not a BytesIO object: {converted_file.name}"
            )
            assert converted_file.stat().st_size > 0, (
                f"Converted file {converted_file.name} is empty"
            )
            with open(converted_file, "rb") as f:
                converted_content = f.read()
            assert file_content.getvalue() == converted_content, (
                f"Content mismatch for file {converted_file.name}"
            )
            
        # Compare filenames and contents for .json files
        for converted_file in converted_json_files:
            # Check if the filename exists in the retrieved files
            assert converted_file.name in nifti_files_dict, (
                f"Filename {converted_file.name} not found in retrieved files"
            )

            file_content = nifti_files_dict[converted_file.name]

            # Check file contents
            assert isinstance(file_content, BytesIO), (
                f"File content is not a BytesIO object: {converted_file.name}"
            )
            assert converted_file.stat().st_size > 0, (
                f"Converted file {converted_file.name} is empty"
            )
            with open(converted_file, "rb") as f:
                converted_content = f.read()
            assert file_content.getvalue() == converted_content, (
                f"Content mismatch for file {converted_file.name}"
            )


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_retrieve_nifti_image(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()

    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)

    adit_client = AditClient(server_url=channels_live_server.url, auth_token=token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    series_uid: str = metadata.iloc[0]["SeriesInstanceUID"]
    image_uid: str = metadata.iloc[0]["SOPInstanceUID"]

    nifti_files = adit_client.retrieve_nifti_image(
        server.ae_title, study_uid, series_uid, image_uid
    )

    assert len(nifti_files) > 0, "No NIfTI files were returned"

    # Normalize filenames returned by retrieve_nifti_image
    nifti_files_dict = {filename: file_content for filename, file_content in nifti_files}
    
    # Check for both .nii.gz and .json files
    nii_files = [f for f in nifti_files_dict.keys() if f.endswith('.nii.gz')]
    json_files = [f for f in nifti_files_dict.keys() if f.endswith('.json')]
    
    assert len(nii_files) > 0, "No .nii.gz files were returned"
    assert len(json_files) > 0, "No .json files were returned"

    # Use DicomToNiftiConverter to convert DICOM files to NIfTI
    sample_dicom_folder = get_sample_dicom_path("1001")
    with tempfile.TemporaryDirectory() as temp_output_folder:
        temp_output_path = Path(temp_output_folder)

        # Create a filtered folder with only the specific image
        filtered_folder = temp_output_path / "filtered"
        filtered_folder.mkdir()

        # Filter DICOM files by SOP instance UID
        image_file = None
        for root, _, files in os.walk(sample_dicom_folder):
            for file in files:
                if not file.endswith(".dcm"):
                    continue
                file_path = Path(root) / file
                try:
                    ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                    if hasattr(ds, "SOPInstanceUID") and ds.SOPInstanceUID == image_uid:
                        image_file = file_path
                        shutil.copy(file_path, filtered_folder / file)
                        break
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
            if image_file:
                break

        assert image_file is not None, f"DICOM file with SOP instance UID {image_uid} not found"

        converter = DicomToNiftiConverter()
        converter.convert(dicom_folder=filtered_folder, output_folder=temp_output_path)

        converted_nii_files = list(temp_output_path.glob("*.nii.gz"))
        converted_json_files = list(temp_output_path.glob("*.json"))
        
        assert len(converted_nii_files) > 0, "No NIfTI files were generated by DicomToNiftiConverter"
        assert len(converted_json_files) > 0, "No JSON files were generated by DicomToNiftiConverter"

        # Compare filenames and contents for .nii.gz files
        for converted_file in converted_nii_files:
            # Check if the filename exists in the retrieved files
            assert converted_file.name in nifti_files_dict, (
                f"Filename {converted_file.name} not found in retrieved files"
            )

            file_content = nifti_files_dict[converted_file.name]

            # Check file contents
            assert isinstance(file_content, BytesIO), (
                f"File content is not a BytesIO object: {converted_file.name}"
            )
            assert converted_file.stat().st_size > 0, (
                f"Converted file {converted_file.name} is empty"
            )
            with open(converted_file, "rb") as f:
                converted_content = f.read()
            assert file_content.getvalue() == converted_content, (
                f"Content mismatch for file {converted_file.name}"
            )
            
        # Compare filenames and contents for .json files
        for converted_file in converted_json_files:
            # Check if the filename exists in the retrieved files
            assert converted_file.name in nifti_files_dict, (
                f"Filename {converted_file.name} not found in retrieved files"
            )

            file_content = nifti_files_dict[converted_file.name]

            # Check file contents
            assert isinstance(file_content, BytesIO), (
                f"File content is not a BytesIO object: {converted_file.name}"
            )
            assert converted_file.stat().st_size > 0, (
                f"Converted file {converted_file.name} is empty"
            )
            with open(converted_file, "rb") as f:
                converted_content = f.read()
            assert file_content.getvalue() == converted_content, (
                f"Content mismatch for file {converted_file.name}"
            )
