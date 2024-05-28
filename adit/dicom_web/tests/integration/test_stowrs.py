import pytest
from adit_client import AditClient
from pydicom import Dataset

from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_stow(
    dimse_orthancs,
    live_server,
    user_with_group_and_token,
    test_dicoms,
):
    _, group, token = user_with_group_and_token
    server: DicomServer = DicomServer.objects.get(ae_title="ORTHANC2")
    # We must also grant access as source as we query the server after
    # the upload if the images are there
    grant_access(group, server, source=True, destination=True)
    adit_client: AditClient = AditClient(server_url=live_server.url, auth_token=token)

    studies: list[Dataset] = adit_client.search_for_studies("ORTHANC2", query={"PatientID": "1001"})
    assert len(studies) == 0, "Orthanc2 should be empty."

    number_of_study_related_instances: dict[str, int] = {}
    for ds in test_dicoms("1001"):
        if ds.StudyInstanceUID not in number_of_study_related_instances:
            number_of_study_related_instances[ds.StudyInstanceUID] = 0
        adit_client.store_instances("ORTHANC2", [ds])
        number_of_study_related_instances[ds.StudyInstanceUID] += 1

    for k, v in number_of_study_related_instances.items():
        results: list[Dataset] = adit_client.search_for_studies(
            "ORTHANC2", query={"StudyInstanceUID": k}
        )
        assert results[0].NumberOfStudyRelatedInstances == v


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_chunked_stow(
    dimse_orthancs,
    live_server,
    user_with_group_and_token,
    test_dicoms,
):
    _, group, token = user_with_group_and_token
    server: DicomServer = DicomServer.objects.get(ae_title="ORTHANC2")
    # We must also grant access as source as we query the server after
    # the upload if the images are there
    grant_access(group, server, source=True, destination=True)
    adit_client: AditClient = AditClient(server_url=live_server.url, auth_token=token)

    studies: list[Dataset] = adit_client.search_for_studies("ORTHANC2", query={"PatientID": "1002"})
    assert len(studies) == 0, "Orthanc2 should be empty."

    number_of_study_related_instances: dict[str, int] = {}
    dataset: list[Dataset] = []
    for ds in test_dicoms("1002"):
        if ds.StudyInstanceUID not in number_of_study_related_instances:
            number_of_study_related_instances[ds.StudyInstanceUID] = 0
        number_of_study_related_instances[ds.StudyInstanceUID] += 1
        dataset += [ds]

    adit_client.store_instances("ORTHANC2", dataset)

    for k, v in number_of_study_related_instances.items():
        results: list[Dataset] = adit_client.search_for_studies(
            "ORTHANC2", query={"StudyInstanceUID": k}
        )
        assert results[0].NumberOfStudyRelatedInstances == v
