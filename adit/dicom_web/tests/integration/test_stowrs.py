import pydicom
import pytest
from dicomweb_client import DICOMwebClient

from adit.accounts.factories import InstituteFactory
from adit.core.factories import DicomNodeInstituteAccessFactory
from adit.core.models import DicomServer


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_stow(
    dimse_orthancs,
    channels_live_server,
    user_with_token,
    create_dicom_web_client,
    test_dicoms,
):
    user, token = user_with_token
    institute = InstituteFactory.create()
    institute.users.add(user)
    server = DicomServer.objects.get(ae_title="ORTHANC2")
    DicomNodeInstituteAccessFactory.create(dicom_node=server, institute=institute, destination=True)
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
