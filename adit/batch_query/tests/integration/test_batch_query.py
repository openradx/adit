import pytest
from playwright.sync_api import Page, expect

from adit.batch_query.models import BatchQueryJob


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_urgent_batch_query_succeeds(
    page: Page,
    setup_orthancs,
    adit_celery_worker,
    channels_liver_server,
    create_and_login_user,
    create_csv_file,
):
    batch_file = create_csv_file(
        [
            ["PatientID", "AccessionNumber"],
            ["1005", "0062115904"],
        ]
    )

    user = create_and_login_user(channels_liver_server.url)
    user.join_group("batch_query_group")
    user.add_permission("can_process_urgently", BatchQueryJob)

    page.goto(channels_liver_server.url + "/batch-query/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Start query urgently").click(force=True)
    page.get_by_label("Project name").fill("Test query")
    page.get_by_label("Project description").fill("Just a test query.")
    page.get_by_label("Batch file").set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()
    expect(page.locator('dl:has-text("Success")').poll()).to_be_visible()
    page.screenshot(path="foo.png")
