import tempfile
from datetime import datetime
from pathlib import Path

import nibabel as nib
import pandas as pd
import pydicom
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
from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import (
    create_dicom_web_client,
    create_excel_file,
    setup_dicomweb_orthancs,
    setup_dimse_orthancs,
)
from adit.dicom_web.utils.testing_helpers import create_user_with_dicom_web_group_and_token


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
    study_uid = "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"
    test_patient_id = "1005"
    df = pd.DataFrame(
        [[test_patient_id, study_uid]],
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
        job_id = current_url.split("/")[-2]  # Extract the job ID from the URL

        run_worker_once()
        page.reload()

        # Validate NIfTI files
        current_date = datetime.now().strftime("%Y%m%d")  # Get the current date dynamically
        expected_folder_name = f"adit_batch_transfer_{job_id}_{current_date}_{user.username}"
        nifti_folder = Path(temp_dir) / expected_folder_name / test_patient_id

        assert nifti_folder.exists(), f"NIfTI folder '{expected_folder_name}' does not exist."
        nifti_files = list(nifti_folder.glob("**/*.nii*"))
        assert len(nifti_files) > 0, "No NIfTI files were generated."

        # Query series description and series number dynamically using dicom_web_client
        _, group, token = create_user_with_dicom_web_group_and_token()
        server = DicomServer.objects.get(ae_title="ORTHANC1")
        grant_access(group, server, source=True)
        dicom_web_client = create_dicom_web_client(live_server.url, server.ae_title, token)

        results = dicom_web_client.retrieve_study_metadata(study_uid)

        expected_filenames = []
        for result_json in results:
            result = pydicom.Dataset.from_json(result_json)
            modality = getattr(result, "Modality", "").strip()
            if modality not in ["CT", "MR", "PT"]:  # Include only imaging modalities
                continue  # Skip non-imaging series
            series_description = getattr(result, "SeriesDescription", "UnknownSeries").strip()
            # Normalize string: replace multiple spaces and special characters
            series_description = "_".join(
                series_description.split()
            )  # Replace multiple spaces with single underscore
            series_description = series_description.replace("/", "_").replace(
                "\\", "_"
            )  # Replace slashes
            series_number = getattr(result, "SeriesNumber", 0)
            expected_filename = f"{series_number}-{series_description}.nii.gz"
            expected_filenames.append(expected_filename)

        # Remove duplicates from expected filenames
        expected_filenames = list(set(expected_filenames))

        # Validate filenames
        for expected_filename in expected_filenames:
            matching_files = [file for file in nifti_files if expected_filename in file.name]
            assert len(matching_files) == 1, f"Expected file '{expected_filename}' not found."

        # Validate NIfTI file content
        for nifti_file in nifti_files:
            try:
                img = nib.load(nifti_file)  # type: ignore # Load the NIfTI file using nibabel
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
