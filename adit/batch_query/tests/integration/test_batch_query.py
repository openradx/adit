from typing import Callable

import pandas as pd
import pytest
from playwright.sync_api import Locator, Page, expect

from adit.accounts.factories import InstituteFactory
from adit.batch_query.models import BatchQueryJob
from adit.core.factories import DicomNodeInstituteAccessFactory


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_urgent_batch_query_with_dimse_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dimse_orthancs,
    adit_celery_worker,
    channels_live_server,
    create_and_login_user,
    create_excel_file,
):
    # Arrange
    df = pd.DataFrame([["1005", "0062115904"]], columns=["PatientID", "AccessionNumber"])
    batch_file = create_excel_file(df)

    user = create_and_login_user(channels_live_server.url)
    user.join_group("batch_query_group")
    user.add_permission("can_process_urgently", BatchQueryJob)
    institute = InstituteFactory.create()
    institute.users.add(user)
    DicomNodeInstituteAccessFactory.create(
        dicom_node=dimse_orthancs[0], institute=institute, source=True
    )
    DicomNodeInstituteAccessFactory.create(
        dicom_node=dimse_orthancs[1], institute=institute, destination=True
    )

    # Act
    page.goto(channels_live_server.url + "/batch-query/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Start query urgently").click(force=True)
    page.get_by_label("Project name").fill("Test query")
    page.get_by_label("Project description").fill("Just a test query.")
    page.get_by_label("Batch file").set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_urgent_batch_query_with_dicomweb_server(
    page: Page,
    poll: Callable[[Locator], Locator],
    dicomweb_orthancs,
    adit_celery_worker,
    channels_live_server,
    create_and_login_user,
    create_excel_file,
):
    # Arrange
    df = pd.DataFrame([["1005", "0062115904"]], columns=["PatientID", "AccessionNumber"])
    batch_file = create_excel_file(df)

    user = create_and_login_user(channels_live_server.url)
    user.join_group("batch_query_group")
    user.add_permission("can_process_urgently", BatchQueryJob)
    institute = InstituteFactory.create()
    institute.users.add(user)
    DicomNodeInstituteAccessFactory.create(
        dicom_node=dicomweb_orthancs[0], institute=institute, source=True
    )
    DicomNodeInstituteAccessFactory.create(
        dicom_node=dicomweb_orthancs[1], institute=institute, destination=True
    )

    # Act
    page.goto(channels_live_server.url + "/batch-query/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Start query urgently").click(force=True)
    page.get_by_label("Project name").fill("Test query")
    page.get_by_label("Project description").fill("Just a test query.")
    page.get_by_label("Batch file").set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    # Assert
    expect(poll(page.locator('dl:has-text("Success")'))).to_be_visible()
