import time
from multiprocessing import Process
import pytest
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from playwright.sync_api import Page, expect
from adit.core.factories import DicomServerFactory
from adit.selective_transfer.models import SelectiveTransferJob


@pytest.fixture
def adit_celery_worker():
    def start_worker():
        call_command("celery_worker", "-Q", "test_queue")

    p = Process(target=start_worker)
    p.start()
    yield
    p.terminate()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_worker(page: Page, adit_celery_worker, channels_liver_server, login_user):

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

    user = login_user(channels_liver_server.url)

    selective_transfer_group = Group.objects.get(name="selective_transfer_group")
    user.groups.add(selective_transfer_group)
    content_type = ContentType.objects.get_for_model(SelectiveTransferJob())
    permission_urgently = Permission.objects.get(
        codename="can_process_urgently", content_type=content_type
    )
    permission_unpseudonymized = Permission.objects.get(
        codename="can_transfer_unpseudonymized", content_type=content_type
    )
    user.user_permissions.add(permission_urgently, permission_unpseudonymized)

    page.goto(channels_liver_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Start transfer directly").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()

    page.locator('a:has-text("ID")').click()
    time.sleep(5)
    page.reload()
    expect(page.locator('dl:has-text("Success")')).to_be_visible()

    page.screenshot(path="foobar.png", full_page=True)
