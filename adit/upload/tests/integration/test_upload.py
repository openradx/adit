from typing import Callable

import pytest
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.auth_utils import add_user_to_group
from playwright.sync_api import Locator, Page, expect

from adit.core.utils.auth_utils import grant_access


@pytest.mark.integration
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

    assert not page.get_by_label("Choose a directory").input_value()


@pytest.mark.integration
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
    page.get_by_label("Choose a directory").set_input_files(
        files=[next(uploadable_test_dicoms("1001"))]
    )

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    page.locator("button#uploadButton").click()

    expect(poll(page.locator("button#stopUploadButton"))).to_be_visible()
    page.locator("button#stopUploadButton").click()

    page.wait_for_selector("p#uploadCompleteText")
    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Cancelled")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_upload_full(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    channels_live_server,
    create_and_login_user,
    upload_group,
    uploadable_test_dicoms,
    test_dicom_paths,
):
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, upload_group)
    grant_access(upload_group, dimse_orthancs[1], destination=True)

    page.on("console", lambda msg: print(msg.text))

    page.goto(channels_live_server.url + "/upload/jobs/new")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").fill("Test pseudonym")
    page.get_by_label("Choose a directory").set_input_files(
        files=[next(uploadable_test_dicoms("1001"))]
    )

    expect(poll(page.locator("button#uploadButton"))).to_be_visible()
    expect(poll(page.locator("button#clearButton"))).to_be_visible()

    # page.screenshot(path="./screenshots/before_upload.png")

    page.locator("button#uploadButton").click()

    expect(poll(page.locator("button#stopUploadButton"))).to_be_visible()

    # page.screenshot(path="./screenshots/during_upload.png")

    page.wait_for_selector("p#uploadCompleteText")

    # page.screenshot(path="./screenshots/after_upload.png")

    expect(page.locator("p#uploadCompleteText")).to_contain_text("Upload Successful!")
