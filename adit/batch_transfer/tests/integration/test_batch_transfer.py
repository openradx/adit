from typing import Callable

import pandas as pd
import pytest
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.auth_utils import add_permission, add_user_to_group
from playwright.sync_api import Locator, Page, expect

from adit.batch_transfer.models import BatchTransferJob
from adit.core.utils.auth_utils import grant_access


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_batch_transfer_with_dimse_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    dicom_worker,
    live_server,
    create_and_login_user,
    batch_transfer_group,
    create_excel_file,
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],  # type: ignore
    )
    batch_file = create_excel_file(df)

    user: User = create_and_login_user(live_server.url)
    add_user_to_group(user, batch_transfer_group)
    add_permission(batch_transfer_group, BatchTransferJob, "can_process_urgently")
    add_permission(batch_transfer_group, BatchTransferJob, "can_transfer_unpseudonymized")
    grant_access(batch_transfer_group, dimse_orthancs[0], source=True)
    grant_access(batch_transfer_group, dimse_orthancs[1], destination=True)

    # Act
    page.goto(live_server.url + "/batch-transfer/jobs/new/")
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
    live_server,
    create_and_login_user,
    batch_transfer_group,
    create_excel_file,
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],  # type: ignore
    )
    batch_file = create_excel_file(df)

    user: User = create_and_login_user(live_server.url)
    add_user_to_group(user, batch_transfer_group)
    add_permission(batch_transfer_group, BatchTransferJob, "can_process_urgently")
    add_permission(batch_transfer_group, BatchTransferJob, "can_transfer_unpseudonymized")
    grant_access(batch_transfer_group, dicomweb_orthancs[0], source=True)
    grant_access(batch_transfer_group, dicomweb_orthancs[1], destination=True)

    # Act
    page.goto(live_server.url + "/batch-transfer/jobs/new/")
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
