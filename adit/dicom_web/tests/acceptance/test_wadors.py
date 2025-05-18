import pydicom
import pytest
from adit_radis_shared.common.utils.testing_helpers import ChannelsLiveServer

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
def test_retrieve_study_with_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    test_pseudonym = "TestPseudonym"
    additional_params = {
        "pseudonym": test_pseudonym,
    }
    results = orthanc1_client.retrieve_study(study_uid, additional_params=additional_params)
    series_uids = set()
    for result in results:
        assert isinstance(result, pydicom.Dataset)
        assert result.StudyInstanceUID == study_uid
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym
        series_uids.add(result.SeriesInstanceUID)
    assert series_uids == set(
        metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    )


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
def test_retrieve_study_metadata_with_pseudonym(
    channels_live_server: ChannelsLiveServer,
):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    test_pseudonym = "TestPseudonym"
    additional_params = {
        "pseudonym": test_pseudonym,
    }

    results = orthanc1_client.retrieve_study_metadata(
        study_uid, additional_params=additional_params
    )
    series_uids = set()
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(result, "PixelData")
        assert result.StudyInstanceUID == study_uid
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym
        series_uids.add(result.SeriesInstanceUID)
    assert series_uids == set(
        metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    )


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
def test_retrieve_series_with_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata.iloc[0]["StudyInstanceUID"]
    series_uid: str = metadata.iloc[0]["SeriesInstanceUID"]
    test_pseudonym = "TestPseudonym"
    additional_params = {
        "pseudonym": test_pseudonym,
    }

    results = orthanc1_client.retrieve_series(
        study_uid, series_uid, additional_params=additional_params
    )
    for result in results:
        assert isinstance(result, pydicom.Dataset)
        assert result.StudyInstanceUID == study_uid
        assert result.SeriesInstanceUID == series_uid
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym


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
def test_retrieve_series_metadata_with_metadata(
    channels_live_server: ChannelsLiveServer,
):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    test_pseudonym = "TestPseudonym"
    additional_params = {
        "pseudonym": test_pseudonym,
    }

    results = orthanc1_client.retrieve_series_metadata(
        study_uid, series_uid, additional_params=additional_params
    )
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(result, "PixelData")
        assert result.StudyInstanceUID == study_uid
        assert result.SeriesInstanceUID == series_uid
        assert result.PatientID == test_pseudonym
        assert result.PatientName == test_pseudonym


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
def test_retrieve_image_with_pseudonym(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]
    test_pseudonym = "TestPseudonym"
    additional_params = {
        "pseudonym": test_pseudonym,
    }

    result = orthanc1_client.retrieve_instance(
        study_uid, series_uid, image_uid, additional_params=additional_params
    )
    assert isinstance(result, pydicom.Dataset)
    assert result.StudyInstanceUID == study_uid
    assert result.SeriesInstanceUID == series_uid
    assert result.SOPInstanceUID == image_uid
    assert result.PatientID == test_pseudonym
    assert result.PatientName == test_pseudonym


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
def test_retrieve_image_metadata_with_pseudonym(
    channels_live_server: ChannelsLiveServer,
):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]
    series_uid: str = metadata["SeriesInstanceUID"].iloc[0]
    image_uid: str = metadata["SOPInstanceUID"].iloc[0]
    test_pseudonym = "TestPseudonym"
    additional_params = {
        "pseudonym": test_pseudonym,
    }

    result = orthanc1_client.retrieve_instance_metadata(
        study_uid, series_uid, image_uid, additional_params=additional_params
    )
    result = pydicom.Dataset.from_json(result)
    assert not hasattr(result, "PixelData")
    assert result.StudyInstanceUID == study_uid
    assert result.SeriesInstanceUID == series_uid
    assert result.SOPInstanceUID == image_uid
    assert result.PatientID == test_pseudonym
    assert result.PatientName == test_pseudonym
