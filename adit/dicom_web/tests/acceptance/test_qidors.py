import pydicom
import pytest
from pytest_django.live_server_helper import LiveServer

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
def test_search_studies(live_server: LiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")

    results = orthanc1_client.search_for_studies()
    results_study_uids = set()
    for result_json in results:
        results_study_uids.add(pydicom.Dataset.from_json(result_json).StudyInstanceUID)
    assert results_study_uids == set(metadata["StudyInstanceUID"])

    results = orthanc1_client.search_for_studies(search_filters={"PatientID": "1005"})
    results_study_uids = set()
    for result_json in results:
        results_study_uids.add(pydicom.Dataset.from_json(result_json).StudyInstanceUID)
    assert results_study_uids == set(metadata[metadata["PatientID"] == "1005"]["StudyInstanceUID"])


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_search_series(live_server: LiveServer):
    setup_dimse_orthancs()

    _, group, token = create_user_with_dicom_web_group_and_token()
    server = DicomServer.objects.get(ae_title="ORTHANC1")
    grant_access(group, server, source=True)
    orthanc1_client = create_dicom_web_client(live_server.url, server.ae_title, token)

    metadata = load_sample_dicoms_metadata("1001")
    study_uid: str = metadata["StudyInstanceUID"].iloc[0]

    results = orthanc1_client.search_for_series(study_uid)
    results_series_uids = set(
        [pydicom.Dataset.from_json(result_json).SeriesInstanceUID for result_json in results]
    )
    assert results_series_uids == set(
        metadata[metadata["StudyInstanceUID"] == study_uid]["SeriesInstanceUID"]
    )

    results = orthanc1_client.search_for_series(study_uid, search_filters={"Modality": "SR"})
    results_series_uids = []
    for result_json in results:
        results_series_uids.append(pydicom.Dataset.from_json(result_json).SeriesInstanceUID)
    assert results_series_uids == list(
        metadata[(metadata["StudyInstanceUID"] == study_uid) & (metadata["Modality"] == "SR")][
            "SeriesInstanceUID"
        ]
    )
