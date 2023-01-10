import pytest
from playwright.sync_api import Page, expect
from adit.selective_transfer.models import SelectiveTransferJob
from adit.groups.models import Access
from adit.core.models import DicomNode
from django.contrib.auth.models import Group



@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer(
    page: Page, setup_orthancs, adit_celery_worker, channels_liver_server, create_and_login_user
):
    
    Group.objects.create(name="DIR")
    Access.objects.create(access_type="src", group=Group.objects.get(name="DIR"), node=DicomNode.objects.get(name="Orthanc Test Server 1"))
    Access.objects.create(access_type="dst", group=Group.objects.get(name="DIR"), node=DicomNode.objects.get(name="Orthanc Test Server 2"))
    
    user = create_and_login_user(channels_liver_server.url)
    user.join_group("DIR")
    user.join_group("selective_transfer_group")
    user.add_permission("can_process_urgently", SelectiveTransferJob)
    user.add_permission("can_transfer_unpseudonymized", SelectiveTransferJob)

    page.goto(channels_liver_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Start transfer directly").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    expect(page.locator('dl:has-text("Success")').poll()).to_be_visible()
