import pydicom
import pytest


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_qido_study(
    setup_orthancs,
    channels_live_server,
    create_dicom_web_client,
    full_data_sheet,
):
    orthanc1_client = create_dicom_web_client(channels_live_server.url, "ORTHANC1")

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
def test_qido_series(
    setup_orthancs,
    channels_live_server,
    create_dicom_web_client,
    extended_data_sheet,
):
    orthanc1_client = create_dicom_web_client(channels_live_server.url, "ORTHANC1")

    results = orthanc1_client.search_for_series()
    results_series_uids = set()
    for result_json in results:
        results_series_uids.add(pydicom.Dataset.from_json(result_json).SeriesInstanceUID)
    assert results_series_uids == set(
        extended_data_sheet["SeriesInstanceUID"]
    ), "Basic QIDO request on series level failed"

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

    results = orthanc1_client.search_for_series()
    results_series_uids = set(
        [pydicom.Dataset.from_json(result_json).SeriesInstanceUID for result_json in results]
    )
    assert results_series_uids == set(
        extended_data_sheet["SeriesInstanceUID"]
    ), "QIDO request with empty StudyInstanceUID on series level failed"

    results = orthanc1_client.search_for_series(search_filters={"Modality": "MR"})
    results_series_uids = set()
    for result_json in results:
        results_series_uids.add(pydicom.Dataset.from_json(result_json).SeriesInstanceUID)
    assert results_series_uids == set(
        extended_data_sheet[extended_data_sheet["Modality"] == "MR"]["SeriesInstanceUID"]
    ), "QIDO request with Modality filter on series level failed"
