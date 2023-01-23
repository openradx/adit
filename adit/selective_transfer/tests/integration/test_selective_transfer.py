import pytest
from django.contrib.auth.models import Group
from playwright.sync_api import Page, expect
from adit.core.models import DicomNode
from adit.groups.models import Access
from adit.selective_transfer.models import SelectiveTransferJob


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer(
    page: Page,
    setup_orthancs,
    adit_celery_worker,
    channels_liver_server,
    create_and_login_user,
):
    group = Group.objects.create(name="DIR")
    
    Access.objects.create(
        access_type="src",
        group=group,
        node=DicomNode.objects.get(name="Orthanc Test Server 1"),
    )
    Access.objects.create(
        access_type="dst",
        group=group,
        node=DicomNode.objects.get(name="Orthanc Test Server 2"),
    )

    user = create_and_login_user(channels_liver_server.url)
    user.join_group("DIR")
    user.join_group("selective_transfer_group")
    user.add_permission("can_process_urgently", SelectiveTransferJob)
    user.add_permission("can_transfer_unpseudonymized", SelectiveTransferJob)

    page.goto(channels_liver_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Start transfer directly").click(force=True)
    breakpoint()
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    expect(page.locator('dl:has-text("Success")').poll()).to_be_visible()





















