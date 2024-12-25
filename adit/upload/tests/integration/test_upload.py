import pytest
from adit_radis_shared.common.utils.testing_helpers import (
    add_user_to_group,
    create_and_login_example_user,
)
from faker import Faker
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.testing_helpers import setup_dimse_orthancs
from adit.upload.utils.testing_helpers import create_upload_group, get_sample_dicoms_folder

fake = Faker()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_clear_files(live_server: LiveServer, page: Page):
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()

    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[1], destination=True)
    folder = get_sample_dicoms_folder("1001")

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    page.get_by_label("Choose a directory").set_input_files(files=[folder])

    assert page.get_by_label("Choose a directory").input_value()

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#clearButton").click()

    expect(page.locator("button#uploadButton")).to_be_hidden()
    expect(page.locator("button#clearButton")).to_be_hidden()
    expect(page.locator("p#fileCountText")).to_be_hidden()

    assert not page.get_by_label("Choose a directory").input_value()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_stop_upload(live_server: LiveServer, page: Page):
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()
    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[1], destination=True)
    folder = get_sample_dicoms_folder("1001")

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    page.get_by_label("Choose a directory").set_input_files(files=[folder])

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(page.locator("button#stopUploadButton")).to_be_visible()
    page.locator("button#stopUploadButton").click()

    page.wait_for_selector("p#uploadCompleteText")
    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Cancelled")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_upload_full(live_server: LiveServer, page: Page):
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()
    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[1], destination=True)
    folder = get_sample_dicoms_folder("1001")

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")

    page.get_by_label("Choose a directory").set_input_files(files=[folder])

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(page.locator("button#stopUploadButton")).to_be_visible()

    page.wait_for_selector("p#uploadCompleteText")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Successful!")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_upload_unsupported_file_type(
    live_server: LiveServer, page: Page, invalid_sample_files_folder: str
):
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()
    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")

    page.get_by_label("Choose a directory").set_input_files(files=[invalid_sample_files_folder])

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#uploadButton").click()
    page.wait_for_selector("p#uploadCompleteText")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Failed due to an Error")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_upload_without_pseudonym(live_server: LiveServer, page: Page):
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()
    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[1], destination=True)
    folder = get_sample_dicoms_folder("1001")

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Choose a directory").set_input_files(files=[folder])

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#uploadButton").click()
    error_message = page.locator("#div_id_pseudonym")

    expect(error_message).to_contain_text("This field is required.")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_upload_without_destination(live_server: LiveServer, page: Page):
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()
    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[1], destination=True)
    folder = get_sample_dicoms_folder("1001")

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    page.get_by_label("Choose a directory").set_input_files(files=[folder])

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#uploadButton").click()
    error_message = page.locator("#div_id_destination")

    expect(error_message).to_contain_text("This field is required.")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_pseudonym_is_used_as_patientID(live_server: LiveServer, page: Page):
    # Arrange
    user = create_and_login_example_user(page, live_server.url)
    group = create_upload_group()
    add_user_to_group(user, group)
    dimse_orthancs = setup_dimse_orthancs()
    grant_access(group, dimse_orthancs[0], destination=True)
    test_pseudonym = "Patient #" + str(fake.random_int(min=10, max=1000))
    folder = get_sample_dicoms_folder("1001")

    page.on("console", lambda msg: print(msg.text))

    page.goto(live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Pseudonym").fill(test_pseudonym)

    page.get_by_label("Choose a directory").set_input_files(files=[folder])

    expect(page.locator("button#uploadButton")).to_be_visible()
    expect(page.locator("button#clearButton")).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(page.locator("button#stopUploadButton")).to_be_visible()

    page.wait_for_selector("p#uploadCompleteText")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Successful!")

    destination_node = dimse_orthancs[0]
    orthanc_operator = DicomOperator(destination_node)
    found_patients = orthanc_operator.find_patients(QueryDataset.create(PatientID=test_pseudonym))
    found_patients_list = list(found_patients)

    assert found_patients_list[0].PatientID == test_pseudonym
    assert found_patients_list[0].NumberOfPatientRelatedStudies == 1
