import pydicom
import pytest
from dicomweb_client import DICOMwebClient


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_wado_study(
    dimse_orthancs,
    channels_live_server,
    create_dicom_web_client,
    extended_data_sheet,
):
    orthanc1_client: DICOMwebClient = create_dicom_web_client(channels_live_server.url, "ORTHANC1")

    study_uid = list(extended_data_sheet["StudyInstanceUID"])[0]

    results = orthanc1_client.retrieve_study(study_uid)
    series_instance_uids = set()
    for result in results:
        assert (
            result.StudyInstanceUID == study_uid
        ), "The WADO request on study level returned series instances of the wrong study."
        series_instance_uids.add(result.SeriesInstanceUID)
    assert series_instance_uids == set(
        extended_data_sheet[extended_data_sheet["StudyInstanceUID"] == study_uid][
            "SeriesInstanceUID"
        ]
    ), "The WADO request on study level did not return all associated series."

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
        extended_data_sheet[extended_data_sheet["StudyInstanceUID"] == study_uid][
            "SeriesInstanceUID"
        ]
    ), "The WADO metadata request on study level did not return all associated series."


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_wado_series(
    dimse_orthancs,
    channels_live_server,
    create_dicom_web_client,
    extended_data_sheet,
):
    orthanc1_client: DICOMwebClient = create_dicom_web_client(channels_live_server.url, "ORTHANC1")

    study_uid = list(extended_data_sheet["StudyInstanceUID"])[0]
    series_uid = list(
        extended_data_sheet[extended_data_sheet["StudyInstanceUID"] == study_uid][
            "SeriesInstanceUID"
        ]
    )[0]

    results = orthanc1_client.retrieve_series(study_uid, series_uid)
    for result in results:
        assert (
            result.StudyInstanceUID == study_uid
        ), "The WADO request on study level returned instances of the wrong study."
        assert (
            result.SeriesInstanceUID == series_uid
        ), "The WADO request on series level returned instances of the wrong series"

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
