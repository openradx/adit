import pydicom
import pytest
from adit_radis_shared.common.utils.testing_helpers import ChannelsLiveServer

from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import (
    create_dicom_web_client,
    get_extended_data_sheet,
    setup_dimse_orthancs,
)
from adit.dicom_web.utils.testing_helpers import create_user_with_dicom_web_group_and_token


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_retrieve_study(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    data_sheet = get_extended_data_sheet()

    study_uid = list(data_sheet["StudyInstanceUID"])[0]

    results = orthanc1_client.retrieve_study(study_uid)
    series_instance_uids = set()
    for result in results:
        assert (
            result.StudyInstanceUID == study_uid
        ), "The WADO request on study level returned series instances of the wrong study."
        series_instance_uids.add(result.SeriesInstanceUID)
    assert series_instance_uids == set(
        data_sheet[data_sheet["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    ), "The WADO request on study level did not return all associated series."


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_retrieve_study_metadata(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    data_sheet = get_extended_data_sheet()

    study_uid = list(data_sheet["StudyInstanceUID"])[0]

    results = orthanc1_client.retrieve_study_metadata(study_uid)
    series_instance_uids = set()
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(
            result, "PixelData"
        ), "The WADO metadata request on study level returned pixel data."
        assert (
            result.StudyInstanceUID == study_uid
        ), "The WADO metadata request on study level returned series instances of the wrong study."
        series_instance_uids.add(result.SeriesInstanceUID)
    assert series_instance_uids == set(
        data_sheet[data_sheet["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    ), "The WADO metadata request on study level did not return all associated series."


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_retrieve_series(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    data_sheet = get_extended_data_sheet()

    study_uid = list(data_sheet["StudyInstanceUID"])[0]
    series_uid = list(data_sheet[data_sheet["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"])[
        0
    ]

    results = orthanc1_client.retrieve_series(study_uid, series_uid)
    for result in results:
        assert (
            result.StudyInstanceUID == study_uid
        ), "The WADO request on study level returned instances of the wrong study."
        assert (
            result.SeriesInstanceUID == series_uid
        ), "The WADO request on series level returned instances of the wrong series"


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_retrieve_series_metadata(channels_live_server: ChannelsLiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(channels_live_server.url, server.ae_title, token)

    data_sheet = get_extended_data_sheet()

    study_uid = list(data_sheet["StudyInstanceUID"])[0]
    series_uid = list(data_sheet[data_sheet["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"])[
        0
    ]

    results = orthanc1_client.retrieve_series_metadata(study_uid, series_uid)
    for result_json in results:
        result = pydicom.Dataset.from_json(result_json)
        assert not hasattr(
            result, "PixelData"
        ), "The WADO metadata request on series level returned pixel data."
        assert (
            result.StudyInstanceUID == study_uid
        ), "The WADO metadata request on series level returned instances of the wrong study."
        assert (
            result.SeriesInstanceUID == series_uid
        ), "The WADO metadata request on series level returned instances of the wrong series"
