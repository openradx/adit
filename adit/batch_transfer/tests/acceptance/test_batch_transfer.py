import tempfile
from datetime import datetime
from pathlib import Path

import nibabel as nib
import pandas as pd
import pytest
from adit_radis_shared.common.utils.testing_helpers import (
    add_permission,
    add_user_to_group,
    create_and_login_example_user,
    run_worker_once,
)
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from adit.batch_transfer.models import BatchTransferJob
from adit.batch_transfer.utils.testing_helpers import create_batch_transfer_group
from adit.core.factories import DicomFolderFactory
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import (
    create_excel_file,
    setup_dicomweb_orthancs,
    setup_dimse_orthancs,
)


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_batch_transfer_with_dimse_server(
    page: Page, live_server: LiveServer
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],  # type: ignore
    )
    batch_file = create_excel_file(df, "batch_file.xlsx")

    user = create_and_login_example_user(page, live_server.url)
    group = create_batch_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, BatchTransferJob, "can_process_urgently")
    add_permission(group, BatchTransferJob, "can_transfer_unpseudonymized")

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Act
    page.goto(live_server.url + "/batch-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Project name").fill("Test transfer")
    page.get_by_label("Project description").fill("Just a test transfer.")
    page.get_by_label("Ethics committee approval").fill("I have it, I swear.")
    page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    run_worker_once()
    page.reload()

    # Assert
    expect(page.locator('dl:has-text("Success")')).to_be_visible()


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_batch_transfer_with_dimse_server_and_convert_to_nifti(
    page: Page, live_server: LiveServer
):
    # Arrange
    test_patient_id = "1005"
    df = pd.DataFrame(
        [[test_patient_id, "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],  # type: ignore
    )
    batch_file = create_excel_file(df, "batch_file.xlsx")

    user = create_and_login_example_user(page, live_server.url)
    group = create_batch_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, BatchTransferJob, "can_process_urgently")
    add_permission(group, BatchTransferJob, "can_transfer_unpseudonymized")

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Use a temporary directory for the NIfTI output
    with tempfile.TemporaryDirectory() as temp_dir:
        download_folder = DicomFolderFactory.create(name="Downloads", path=temp_dir)
        grant_access(group, download_folder, destination=True)

        # Act
        page.goto(live_server.url + "/batch-transfer/jobs/new/")
        page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
        page.get_by_label("Destination").select_option(label="DICOM Folder Downloads")
        page.get_by_label("Urgent").click(force=True)
        page.get_by_label("Convert to NIfTI").click(force=True)  # Enable NIfTI conversion
        page.get_by_label("Project name").fill("Test transfer with NIfTI conversion (DIMSE)")
        page.get_by_label("Project description").fill(
            "Testing transfer with NIfTI conversion using DIMSE."
        )
        page.get_by_label("Ethics committee approval").fill("I have it, I swear.")
        page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
        page.locator('input:has-text("Create job")').click()

        # Extract the job ID from the URL
        current_url = page.url
        job_id = current_url.split("/")[
            -2
        ]  # Extract the job ID from the URL (e.g., /batch-transfer/jobs/<jobID>/)

        run_worker_once()
        page.reload()

        # Validate NIfTI files
        current_date = datetime.now().strftime("%Y%m%d")  # Get the current date dynamically
        expected_folder_name = f"adit_batch_transfer_{job_id}_{current_date}_{user.username}"
        nifti_folder = Path(temp_dir) / expected_folder_name / test_patient_id

        assert nifti_folder.exists(), f"NIfTI folder '{expected_folder_name}' does not exist."
        nifti_files = list(nifti_folder.glob("**/*.nii*"))
        assert len(nifti_files) > 0, "No NIfTI files were generated."

        for nifti_file in nifti_files:
            try:
                img = nib.load(nifti_file)  # type: ignore
                assert img is not None, f"Invalid NIfTI file: {nifti_file}"
            except Exception as e:
                raise AssertionError(f"Failed to validate NIfTI file {nifti_file}: {e}")

        # Assert
        expect(page.locator('dl:has-text("Success")')).to_be_visible()


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_batch_transfer_with_dicomweb_server(
    page: Page, live_server: LiveServer
):
    # Arrange
    df = pd.DataFrame(
        [["1005", "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"]],
        columns=["PatientID", "StudyInstanceUID"],  # type: ignore
    )
    batch_file = create_excel_file(df, "batch_file.xlsx")

    user = create_and_login_example_user(page, live_server.url)
    group = create_batch_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, BatchTransferJob, "can_process_urgently")
    add_permission(group, BatchTransferJob, "can_transfer_unpseudonymized")

    orthancs = setup_dicomweb_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Act
    page.goto(live_server.url + "/batch-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Project name").fill("Test transfer")
    page.get_by_label("Project description").fill("Just a test transfer.")
    page.get_by_label("Ethics committee approval").fill("I have it, I swear.")
    page.get_by_label("Batch file*", exact=True).set_input_files(files=[batch_file])
    page.locator('input:has-text("Create job")').click()

    run_worker_once()
    page.reload()

    # Assert
    expect(page.locator('dl:has-text("Success")')).to_be_visible()
