import pydicom
import pytest
from requests.exceptions import HTTPError


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_stow(
    setup_orthancs,
    channels_live_server,
    create_dicom_web_client,
    test_dicoms,
):
    orthanc2_client = create_dicom_web_client(channels_live_server.url, "ORTHANC2")

    with pytest.raises(HTTPError) as err:
        orthanc2_client.search_for_series()
    assert err.value.response.status_code == 404, "Orthanc2 should be empty."

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
