from typing import Callable

import pytest
from playwright.sync_api import Locator, Page, expect

from adit.core.utils.auth_utils import grant_access
from adit.selective_transfer.models import SelectiveTransferJob
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.auth_utils import add_permission, add_user_to_group


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer_with_dimse_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    dicom_worker,
    channels_live_server,
    create_and_login_user,
    selective_transfer_group,
):
    # Arrange
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, selective_transfer_group)
    add_permission(selective_transfer_group, SelectiveTransferJob, "can_process_urgently")
    add_permission(selective_transfer_group, SelectiveTransferJob, "can_transfer_unpseudonymized")
    grant_access(selective_transfer_group, dimse_orthancs[0], source=True)
    grant_access(selective_transfer_group, dimse_orthancs[1], destination=True)

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer_with_dicomweb_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dicomweb_orthancs,
    dicom_worker,
    channels_live_server,
    create_and_login_user,
    selective_transfer_group,
):
    # Arrange
    user: User = create_and_login_user(channels_live_server.url)
    add_user_to_group(user, selective_transfer_group)
    add_permission(selective_transfer_group, SelectiveTransferJob, "can_process_urgently")
    add_permission(selective_transfer_group, SelectiveTransferJob, "can_transfer_unpseudonymized")
    grant_access(selective_transfer_group, dicomweb_orthancs[0], source=True)
    grant_access(selective_transfer_group, dicomweb_orthancs[1], destination=True)

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()
