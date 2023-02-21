import pytest
from django.contrib.auth.models import Group
from playwright.sync_api import Page, expect
from adit.core.factories import DicomServerFactory
from adit.core.models import DicomNode
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
    Access.objects.create(access_type="src",
                          group=groupDIR,
                          node=DicomNode.objects.get(name="Node 0"))
    Access.objects.create(access_type="dst",
                          group=groupDIR,
                          node=DicomNode.objects.get(name="Node 0"))
    Access.objects.create(access_type="src",
                          group=groupDIR,
                          node=DicomNode.objects.get(name="Node 1"))
    Access.objects.create(access_type="src",
                          group=groupDIR,
                          node=DicomNode.objects.get(name="Node 2"))
    Access.objects.create(access_type="dst",
                          group=groupDIR,
                          node=DicomNode.objects.get(name="Node 3"))
    

    # Log in as user with group membership
    user2 = create_and_login_user(channels_liver_server.url)
    user2.join_group("dicom_explorer_group")
    user2.join_group('DIR')

    # Go to Batch-Transfer page
    page.goto(channels_liver_server.url + "/dicom-explorer/")
    
    # Check that the user can access all dicom nodes for source and destination
    # where he has access to
    locSrc = page.get_by_label("Server")
    expect(locSrc).to_contain_text("Node 0")
    expect(locSrc).to_contain_text("Node 1")
    expect(locSrc).to_contain_text("Node 2")
    expect(locSrc).not_to_contain_text("Node 3")

    # Log out
    page.goto(channels_liver_server.url + "/accounts/logout/")


    # Log in as user without group membership
    user2 = create_and_login_user(channels_liver_server.url)
    user2.join_group("dicom_explorer_group")
    
    # Check that the user can access all dicom nodes for source and destination
    page.goto(channels_liver_server.url + "/dicom-explorer/")
    
    # breakpoint()
    locSrc = page.get_by_label("Server")
    expect(locSrc).not_to_contain_text("Node 0")
    expect(locSrc).not_to_contain_text("Node 1")
    expect(locSrc).not_to_contain_text("Node 2")
    expect(locSrc).not_to_contain_text("Node 3")

    # Log out
    page.goto(channels_liver_server.url + "/accounts/logout/")