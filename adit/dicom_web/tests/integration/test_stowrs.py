import pydicom
import pytest
from dicomweb_client import DICOMwebClient

from adit.core.models import DicomServer


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_stow(
    dimse_orthancs,
    channels_live_server,
    user_with_token,
    grant_access,
    create_dicom_web_client,
    test_dicoms,
):
    user, token = user_with_token
    server = DicomServer.objects.get(ae_title="ORTHANC2")
    # We must also grant access as source as we query the server after
    # the upload if the images are there
    grant_access(user, server, "source")
    grant_access(user, server, "destination")
    orthanc2_client: DICOMwebClient = create_dicom_web_client(
        channels_live_server.url, server.ae_title
    )

    studies = orthanc2_client.search_for_studies()
    assert len(studies) == 0, "Orthanc2 should be empty."

    uploaded_series = {}
    for ds in test_dicoms:
        if ds.SeriesInstanceUID not in uploaded_series:
            uploaded_series[ds.SeriesInstanceUID] = {
                "number_instances": 0,
                "study_uid": ds.StudyInstanceUID,
            }
        orthanc2_client.store_instances([ds])
        uploaded_series[ds.SeriesInstanceUID]["number_instances"] += 1

    for series_uid, series_dict in uploaded_series.items():
        results = orthanc2_client.search_for_series(
            series_dict["study_uid"], search_filters={"SeriesInstanceUID": series_uid}
        )
        result_ds = pydicom.Dataset.from_json(results[0])
        assert (
            result_ds.NumberOfSeriesRelatedInstances == series_dict["number_instances"]
        ), "Number of instances in series does not match number of uploaded instances."
