import pydicom
import pytest
from dicomweb_client import DICOMwebClient

from adit.core.models import DicomServer


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_wado_study(
    dimse_orthancs,
    channels_live_server,
    user_with_token,
    grant_access,
    create_dicom_web_client,
    extended_data_sheet,
) -> None:
    user, token = user_with_token
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(user, server, "source")
    orthanc1_client: DICOMwebClient = create_dicom_web_client(
        channels_live_server.url, server.ae_title
    )

    study_uid = list(extended_data_sheet["StudyInstanceUID"])[0]

    studies: list[pydicom.Dataset] = orthanc1_client.retrieve_study(study_uid)
    series_instance_uids = set()
    for study in studies:
        assert (
            study.StudyInstanceUID == study_uid
        ), "The WADO request on study level returned series instances of the wrong study."
        series_instance_uids.add(study.SeriesInstanceUID)
    assert series_instance_uids == set(
        extended_data_sheet[extended_data_sheet["StudyInstanceUID"] == study_uid][
            "SeriesInstanceUID"
        ]
    ), "The WADO request on study level did not return all associated series."

    metadata_list = orthanc1_client.retrieve_study_metadata(study_uid)
    series_instance_uids = set()
    for metadata in metadata_list:
        study_ds = pydicom.Dataset.from_json(metadata)
        assert not hasattr(
            study_ds, "PixelData"
        ), "The WADO metadata request on study level returned pixel data."
        assert (
            study_ds.StudyInstanceUID == study_uid
        ), "The WADO metadata request on study level returned series instances of the wrong study."
        series_instance_uids.add(study_ds.SeriesInstanceUID)
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
    user_with_token,
    grant_access,
    create_dicom_web_client,
    extended_data_sheet,
) -> None:
    user, token = user_with_token
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(user, server, "source")
    orthanc1_client: DICOMwebClient = create_dicom_web_client(
        channels_live_server.url, server.ae_title
    )

    study_uid = list(extended_data_sheet["StudyInstanceUID"])[0]
    series_uid = list(
        extended_data_sheet[extended_data_sheet["StudyInstanceUID"] == study_uid][
            "SeriesInstanceUID"
        ]
    )[0]

    series_list = orthanc1_client.retrieve_series(study_uid, series_uid)
    for series in series_list:
        assert (
            series.StudyInstanceUID == study_uid
        ), "The WADO request on study level returned instances of the wrong study."
        assert (
            series.SeriesInstanceUID == series_uid
        ), "The WADO request on series level returned instances of the wrong series"

    metadata_list = orthanc1_client.retrieve_series_metadata(study_uid, series_uid)
    for metadata in metadata_list:
        series_ds = pydicom.Dataset.from_json(metadata)
        assert not hasattr(
            series_ds, "PixelData"
        ), "The WADO metadata request on series level returned pixel data."
        assert (
            series_ds.StudyInstanceUID == study_uid
        ), "The WADO metadata request on series level returned instances of the wrong study."
        assert (
            series_ds.SeriesInstanceUID == series_uid
        ), "The WADO metadata request on series level returned instances of the wrong series"
