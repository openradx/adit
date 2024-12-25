from typing import Callable

import pandas as pd
import pytest
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.auth_utils import add_permission, add_user_to_group
from adit_radis_shared.common.utils.worker_utils import run_worker_once
from playwright.sync_api import Locator, Page, expect

from adit.batch_query.models import BatchQueryJob
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import (
    create_excel_file,
    setup_dicomweb_orthancs,
    setup_dimse_orthancs,
)


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_urgent_batch_query_with_dimse_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    live_server,
    create_and_login_user,
    batch_query_group,
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "0062115904"]],
        columns=["PatientID", "AccessionNumber"],  # type: ignore
    )
    batch_file = create_excel_file(df, "batch_file.xlsx")

    user: User = create_and_login_user(live_server.url)
    add_user_to_group(user, batch_query_group)
    add_permission(batch_query_group, BatchQueryJob, "can_process_urgently")

    orthancs = setup_dimse_orthancs()
    grant_access(batch_query_group, orthancs[0], source=True)
    grant_access(batch_query_group, orthancs[1], destination=True)

    # Act
    page.goto(live_server.url + "/batch-query/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Project name").fill("Test query")
    page.get_by_label("Project description").fill("Just a test query.")
    page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    run_worker_once()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_urgent_batch_query_with_dicomweb_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    live_server,
    create_and_login_user,
    batch_query_group,
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "0062115904"]],
        columns=["PatientID", "AccessionNumber"],  # type: ignore
    )
    batch_file = create_excel_file(df, "batch_file.xlsx")

    user: User = create_and_login_user(live_server.url)
    add_user_to_group(user, batch_query_group)
    add_permission(batch_query_group, BatchQueryJob, "can_process_urgently")

    orthancs = setup_dicomweb_orthancs()
    grant_access(batch_query_group, orthancs[0], source=True)
    grant_access(batch_query_group, orthancs[1], destination=True)

    # Act
    page.goto(live_server.url + "/batch-query/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Project name").fill("Test query")
    page.get_by_label("Project description").fill("Just a test query.")
    page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    run_worker_once()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()
