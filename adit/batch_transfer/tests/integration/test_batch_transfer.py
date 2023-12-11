from typing import Callable

import pandas as pd
import pytest
from playwright.sync_api import Locator, Page, expect

from adit.batch_transfer.models import BatchTransferJob


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_batch_transfer_with_dimse_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    dicom_worker,
    channels_live_server,
    create_and_login_user,
    grant_access,
    create_excel_file,
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],
    )
    batch_file = create_excel_file(df)

    user = create_and_login_user(channels_live_server.url)
    user.join_group("batch_transfer_group")
    user.add_permission("can_process_urgently", BatchTransferJob)
    user.add_permission("can_transfer_unpseudonymized", BatchTransferJob)
    grant_access(user, dimse_orthancs[0], "source")
    grant_access(user, dimse_orthancs[1], "destination")

    # Act
    page.goto(channels_live_server.url + "/batch-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Project name").fill("Test transfer")
    page.get_by_label("Project description").fill("Just a test transfer.")
    page.get_by_label("Ethics committee approval").fill("I have it, I swear.")
    page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_batch_transfer_with_dicomweb_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dicomweb_orthancs,
    dicom_worker,
    channels_live_server,
    create_and_login_user,
    grant_access,
    create_excel_file,
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],
    )
    batch_file = create_excel_file(df)

    user = create_and_login_user(channels_live_server.url)
    user.join_group("batch_transfer_group")
    user.add_permission("can_process_urgently", BatchTransferJob)
    user.add_permission("can_transfer_unpseudonymized", BatchTransferJob)
    grant_access(user, dicomweb_orthancs[0], "source")
    grant_access(user, dicomweb_orthancs[1], "destination")

    # Act
    page.goto(channels_live_server.url + "/batch-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Project name").fill("Test transfer")
    page.get_by_label("Project description").fill("Just a test transfer.")
    page.get_by_label("Ethics committee approval").fill("I have it, I swear.")
    page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()
