import pytest
from django.contrib.auth.models import Group
from playwright.sync_api import Page, expect
from adit.batch_transfer.models import BatchTransferJob
from adit.core.factories import DicomServerFactory
from adit.core.models import DicomNode, DicomServer
from adit.groups.models import Access


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_access_levels(
    page: Page,
    setup_orthancs,
    adit_celery_worker,
    channels_liver_server,
    create_and_login_user,
):
    # Create Group which gets access to DicomNodes
    groupDIR = Group.objects.create(name="DIR")

    # Create DicomNodes
    DicomServerFactory(name="Node 0", ae_title="NODE0",)
    DicomServerFactory(name="Node 1", ae_title="NODE1",)
    DicomServerFactory(name="Node 2", ae_title="NODE2",)
    DicomServerFactory(name="Node 3", ae_title="NODE3",)

    # Create Access objects for each DicomNode
    Access.objects.create(access_type="src", group=groupDIR, node=DicomNode.objects.get(name="Node 0"))
    Access.objects.create(access_type="dst", group=groupDIR, node=DicomNode.objects.get(name="Node 0"))
    Access.objects.create(access_type="src", group=groupDIR, node=DicomNode.objects.get(name="Node 1"))
    Access.objects.create(access_type="src", group=groupDIR, node=DicomNode.objects.get(name="Node 2"))
    Access.objects.create(access_type="dst", group=groupDIR, node=DicomNode.objects.get(name="Node 3") )
    
    # Log in as user with group membership
    user2 = create_and_login_user(channels_liver_server.url)
    user2.join_group("batch_transfer_group")
    user2.join_group('DIR')
    user2.add_permission("can_process_urgently", BatchTransferJob)
    user2.add_permission("can_transfer_unpseudonymized", BatchTransferJob)

    # Go to Batch-Transfer page
    page.goto(channels_liver_server.url + "/batch-transfer/jobs/new/")
    
    # Check that the user can access all dicom nodes for source and destination
    # where he has access to
    locSrc = page.get_by_label("Source")
    expect(locSrc).to_contain_text("Node 0")
    expect(locSrc).to_contain_text("Node 1")
    expect(locSrc).to_contain_text("Node 2")
    expect(locSrc).not_to_contain_text("Node 3")

    locDst = page.get_by_label("Destination")
    expect(locDst).not_to_contain_text("Node 1")
    expect(locDst).not_to_contain_text("Node 2")
    expect(locDst).to_contain_text("Node 0")
    expect(locDst).to_contain_text("Node 3")
    
    # Log out
    page.goto(channels_liver_server.url + "/accounts/logout/")


    # Log in as user without group membership
    user2 = create_and_login_user(channels_liver_server.url)
    user2.join_group("batch_transfer_group")
    user2.add_permission("can_process_urgently", BatchTransferJob)
    user2.add_permission("can_transfer_unpseudonymized", BatchTransferJob)

    # Check that the user can access all dicom nodes for source and destination
    page.goto(channels_liver_server.url + "/batch-transfer/jobs/new/")
    
    # breakpoint()
    locSrc = page.get_by_label("Source")
    expect(locSrc).not_to_contain_text("Node 0")
    expect(locSrc).not_to_contain_text("Node 1")
    expect(locSrc).not_to_contain_text("Node 2")
    expect(locSrc).not_to_contain_text("Node 3")

    locDst = page.get_by_label("Destination")
    expect(locDst).not_to_contain_text("Node 0")
    expect(locDst).not_to_contain_text("Node 1")
    expect(locDst).not_to_contain_text("Node 2")
    expect(locDst).not_to_contain_text("Node 3")
    
    # Log out
    page.goto(channels_liver_server.url + "/accounts/logout/")


    
