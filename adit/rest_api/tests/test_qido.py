from pydicom.dataset import Dataset


def test_qido_studies(dicom_web_client, orthanc1_test_study_uids):
    response = dicom_web_client.search_for_studies()
    study_uids = []
    for study in response:
        study_uids.append(Dataset.from_json(study).StudyInstanceUID)

    for test_study_uid in orthanc1_test_study_uids:
        assert test_study_uid in study_uids


def test_qido_series(dicom_web_client, orthanc1_test_study_with_series_uids):
    response = dicom_web_client.search_for_series(orthanc1_test_study_with_series_uids[0])
    series_uids = []
    for series in response:
        series_uids.append(Dataset.from_json(series).SeriesInstanceUID)

    for test_series_uid in orthanc1_test_study_with_series_uids[1]:
        assert test_series_uid in series_uids


def test_qido_filter(dicom_web_client, orthanc1_test_patient_ids):
    response = dicom_web_client.search_for_studies(
        search_filters={"PatientID": orthanc1_test_patient_ids[0]}
    )
    study_patient_ids = []
    for study in response:
        study_patient_ids.append(Dataset.from_json(study).PatientID)
