from datetime import datetime
from pathlib import Path

import nibabel as nib
import pytest
from adit_radis_shared.common.utils.testing_helpers import (
    ChannelsLiveServer,
    add_permission,
    add_user_to_group,
    create_and_login_example_user,
    run_worker_once,
)
from playwright.sync_api import Page, expect

from adit.core.factories import DicomFolderFactory
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import setup_dicomweb_orthancs, setup_dimse_orthancs
from adit.selective_transfer.models import SelectiveTransferJob
from adit.selective_transfer.utils.testing_helpers import create_selective_transfer_group


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer_with_dimse_server(
    page: Page, channels_live_server: ChannelsLiveServer
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, SelectiveTransferJob, "can_process_urgently")
    add_permission(group, SelectiveTransferJob, "can_transfer_unpseudonymized")

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").click()
    page.get_by_label("Patient ID").fill("1008")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    run_worker_once()
    page.reload()

    # Assert
    expect(page.locator('dl:has-text("Success")')).to_be_visible()


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_unpseudonymized_urgent_selective_transfer_with_dimse_server_and_convert_to_nifti(
    page: Page, channels_live_server: ChannelsLiveServer
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, SelectiveTransferJob, "can_process_urgently")
    add_permission(group, SelectiveTransferJob, "can_transfer_unpseudonymized")

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)
    download_folder = DicomFolderFactory.create(name="Downloads", path="/app/dicom_downloads")
    grant_access(group, download_folder, destination=True)

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Convert to NIfTI").click(force=True)  # Enable NIfTI conversion
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Folder Downloads")
    page.get_by_label("Patient ID").click()
    page.get_by_label("Patient ID").fill("1008")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()

    # Extract the job ID from the success message
    success_message = page.locator("text=Successfully submitted transfer job with ID").inner_text()
    job_id = int(success_message.split("ID")[-1].strip())

    page.locator('a:has-text("ID")').click()

    run_worker_once()
    page.reload()

    # Validate NIfTI files
    current_date = datetime.now().strftime("%Y%m%d")  # Get the current date dynamically
    expected_folder_name = f"adit_selective_transfer_{job_id}_{current_date}_{user.username}"
    nifti_folder_base = Path("/app/dicom_downloads/")
    nifti_folder = nifti_folder_base / expected_folder_name

    assert nifti_folder.exists(), f"NIfTI folder '{expected_folder_name}' does not exist."
    nifti_files = list(nifti_folder.glob("*.nii*"))
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
def test_unpseudonymized_urgent_selective_transfer_with_dicomweb_server(
    page: Page, channels_live_server: ChannelsLiveServer
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, SelectiveTransferJob, "can_process_urgently")
    add_permission(group, SelectiveTransferJob, "can_transfer_unpseudonymized")

    orthancs = setup_dicomweb_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Urgent").click(force=True)
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").click()
    page.get_by_label("Patient ID").fill("1008")
    page.get_by_label("Patient ID").press("Enter")
    page.locator('tr:has-text("1008"):has-text("2020") input').click()
    page.locator('button:has-text("Start transfer")').click()
    page.locator('a:has-text("ID")').click()

    run_worker_once()
    page.reload()

    # Assert
    expect(page.locator('dl:has-text("Success")')).to_be_visible()
