from typing import Callable

import pytest
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.auth_utils import add_user_to_group
from faker import Faker
from playwright.sync_api import Locator, Page, expect

from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator

fake = Faker()


@pytest.mark.django_db(transaction=True)
def test_clear_files(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))

    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    file = next(uploadable_test_dicoms("1001"))
    page.get_by_label("Choose a directory").set_input_files(files=[file])

    assert page.get_by_label("Choose a directory").input_value()

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#clearButton").click()

    expect(page.locator("button#uploadButton")).to_be_hidden()
    expect(page.locator("button#clearButton")).to_be_hidden()
    expect(page.locator("p#fileCountText")).to_be_hidden()

    assert not page.get_by_label("Choose a directory").input_value()


@pytest.mark.django_db(transaction=True)
def test_stop_upload(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))

    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    file = next(uploadable_test_dicoms("1001"))
    page.get_by_label("Choose a directory").set_input_files(files=[file])

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(poll(page.locator("button#stopUploadButton"))).to_be_visible()
    page.locator("button#stopUploadButton").click()

    page.wait_for_selector("p#uploadCompleteText")
    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Cancelled")


@pytest.mark.django_db(transaction=True)
def test_upload_full(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))

    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    file = next(uploadable_test_dicoms("1001"))

    page.get_by_label("Choose a directory").set_input_files(files=[file])

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(poll(page.locator("button#stopUploadButton"))).to_be_visible()

    page.wait_for_selector("p#uploadCompleteText")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Successful!")


@pytest.mark.django_db(transaction=True)
def test_upload_unsupported_file_type(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    noncompatible_test_file,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))

    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")

    tmp = noncompatible_test_file()
    page.get_by_label("Choose a directory").set_input_files(files=[tmp])

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()
    page.wait_for_selector("p#uploadCompleteText")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Failed due to an Error")


@pytest.mark.django_db(transaction=True)
def test_upload_without_pseudonym(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)
    page.on("console", lambda msg: print(msg.text))
    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    file = next(uploadable_test_dicoms("1001"))
    page.get_by_label("Choose a directory").set_input_files(files=[file])

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()
    error_message = page.locator("#div_id_pseudonym")

    expect(error_message).to_contain_text("This field is required.")


@pytest.mark.django_db(transaction=True)
def test_upload_without_destination(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))
    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    file = next(uploadable_test_dicoms("1001"))
    page.get_by_label("Choose a directory").set_input_files(files=[file])

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()
    error_message = page.locator("#div_id_destination")

    expect(error_message).to_contain_text("This field is required.")


@pytest.mark.django_db(transaction=True)
def test_pseudonym_is_used_as_patientID(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
):
    # Arrange
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))
    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")

    test_pseudonym = "Patient #" + str(fake.random_int(min=10, max=1000))
    page.get_by_label("Pseudonym").fill(test_pseudonym)

    file = next(uploadable_test_dicoms("1001"))

    page.get_by_label("Choose a directory").set_input_files(files=[file])

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(poll(page.locator("button#stopUploadButton"))).to_be_visible()

    page.wait_for_selector("p#uploadCompleteText")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Successful!")

    destination_node = DicomServer.objects.get(id="14")
    orthanc_operator = DicomOperator(destination_node)
    found_patients = orthanc_operator.find_patients(QueryDataset.create(PatientID=test_pseudonym))
    found_patients_list = list(found_patients)

    assert found_patients_list[0].PatientID == test_pseudonym
    assert found_patients_list[0].NumberOfPatientRelatedStudies == 1