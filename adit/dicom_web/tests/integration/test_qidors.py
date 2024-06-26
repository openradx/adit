import pydicom
import pytest
from dicomweb_client import DICOMwebClient

from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_search_studies(
    dimse_orthancs,
    live_server,
    user_with_group_and_token,
    create_dicom_web_client,
    full_data_sheet,
):
    _, group, token = user_with_group_and_token
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client: DICOMwebClient = create_dicom_web_client(
        live_server.url, server.ae_title, token
    )

    results = orthanc1_client.search_for_studies()
    results_study_uids = set()
    for result_json in results:
        results_study_uids.add(pydicom.Dataset.from_json(result_json).StudyInstanceUID)
    assert results_study_uids == set(
        full_data_sheet["StudyInstanceUID"]
    ), "Basic QIDO request on study level failed."

    results = orthanc1_client.search_for_studies(search_filters={"PatientID": "1005"})
    results_study_uids = set()
    for result_json in results:
        results_study_uids.add(pydicom.Dataset.from_json(result_json).StudyInstanceUID)
    assert results_study_uids == set(
        full_data_sheet[full_data_sheet["PatientID"] == 1005]["StudyInstanceUID"]
    ), "QIDO request with PatientID filter on study level failed."


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_search_series(
    dimse_orthancs,
    live_server,
    user_with_group_and_token,
    create_dicom_web_client,
    extended_data_sheet,
):
    _, group, token = user_with_group_and_token
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client: DICOMwebClient = create_dicom_web_client(
        live_server.url, server.ae_title, token
    )

    study_uid = list(extended_data_sheet["StudyInstanceUID"])[0]
    results = orthanc1_client.search_for_series(study_uid)
    results_series_uids = set(
        [pydicom.Dataset.from_json(result_json).SeriesInstanceUID for result_json in results]
    )
    assert results_series_uids == set(
        extended_data_sheet[extended_data_sheet["StudyInstanceUID"] == study_uid][
            "SeriesInstanceUID"
        ]
    ), "QIDO request with StudyInstanceUID on series level failed"

    results = orthanc1_client.search_for_series(study_uid, search_filters={"Modality": "SR"})
    results_series_uids = list()
    for result_json in results:
        results_series_uids.append(pydicom.Dataset.from_json(result_json).SeriesInstanceUID)
    assert len(results_series_uids) == 1
    assert (
        results_series_uids[0] == list(extended_data_sheet["SeriesInstanceUID"])[3]
    ), "QIDO request with StudyInstanceUID and Modality filter on series level failed"
