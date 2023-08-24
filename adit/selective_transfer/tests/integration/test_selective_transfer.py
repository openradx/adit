from typing import Callable

import pytest
from playwright.sync_api import Locator, Page, expect

from adit.selective_transfer.models import SelectiveTransferJob


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer_with_dimse_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    adit_celery_worker,
    channels_live_server,
    create_and_login_user,
    grant_access,
):
    # Arrange
    user = create_and_login_user(channels_live_server.url)
    user.join_group("selective_transfer_group")
    user.add_permission("can_process_urgently", SelectiveTransferJob)
    user.add_permission("can_transfer_unpseudonymized", SelectiveTransferJob)
    grant_access(user, dimse_orthancs[0], "source")
    grant_access(user, dimse_orthancs[1], "destination")

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Start transfer directly").click(force=True)
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
    adit_celery_worker,
    channels_live_server,
    create_and_login_user,
    grant_access,
):
    # Arrange
    user = create_and_login_user(channels_live_server.url)
    user.join_group("selective_transfer_group")
    user.add_permission("can_process_urgently", SelectiveTransferJob)
    user.add_permission("can_transfer_unpseudonymized", SelectiveTransferJob)
    grant_access(user, dicomweb_orthancs[0], "source")
    grant_access(user, dicomweb_orthancs[1], "destination")

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Start transfer directly").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()
