import pytest
from django.conf import settings
from playwright.sync_api import Page, expect
from adit.accounts.utils import UserPermissionManager
from adit.core.factories import DicomServerFactory
from adit.selective_transfer.models import SelectiveTransferJob


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_selective_transfer(
    page: Page, adit_celery_worker, channels_liver_server, create_and_login_user
):
    DicomServerFactory(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        host=settings.ORTHANC1_HOST,
        port=settings.ORTHANC1_DICOM_PORT,
    )
    DicomServerFactory(
        name="Orthanc Test Server 2",
        ae_title="ORTHANC2",
        host=settings.ORTHANC2_HOST,
        port=settings.ORTHANC2_DICOM_PORT,
    )

    user = create_and_login_user(channels_liver_server.url)

    manager = UserPermissionManager(user)
    manager.add_group("selective_transfer_group")
    manager.add_permission("can_process_urgently", SelectiveTransferJob)
    manager.add_permission("can_transfer_unpseudonymized", SelectiveTransferJob)

    page.goto(channels_liver_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Start transfer directly").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()
    expect(page.locator('dl:has-text("Success")').poll()).to_be_visible()

    page.screenshot(path="foobar.png", full_page=True)
