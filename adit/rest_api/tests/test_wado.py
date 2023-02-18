from pydicom.dataset import Dataset


def test_wado_study_metadata(dicom_web_client, orthanc1_test_study_with_series_uids):
    response = dicom_web_client.retrieve_study_metadata(orthanc1_test_study_with_series_uids[0])
    for series in response:
        ds = Dataset.from_json(series)
        for elem in ds:
            assert "0002" in str(elem.tag)


def test_wado_study(dicom_web_client, orthanc1_test_study_with_series_uids):
    response = dicom_web_client.retrieve_study(orthanc1_test_study_with_series_uids[0])
    series_uids = []
    for series in response:
        series_uids.append(series.SeriesInstanceUID)

    for test_series_uid in orthanc1_test_study_with_series_uids[1]:
        assert test_series_uid in series_uids


def test_wado_series(dicom_web_client, orthanc1_test_study_with_series_uids):
    response = dicom_web_client.retrieve_series(
        orthanc1_test_study_with_series_uids[0],
        orthanc1_test_study_with_series_uids[1][1],
    )
    for series in response:
        assert orthanc1_test_study_with_series_uids[1][1] == series.SeriesInstanceUID
