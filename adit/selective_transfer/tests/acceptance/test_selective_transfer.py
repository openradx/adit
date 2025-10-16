import io
import tempfile
import zipfile
from collections import Counter
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
from django.utils import timezone
from playwright.sync_api import Page, expect

from adit.core.factories import DicomFolderFactory
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import setup_dicomweb_orthancs, setup_dimse_orthancs
from adit.selective_transfer.models import SelectiveTransferJob
from adit.selective_transfer.utils.testing_helpers import create_selective_transfer_group


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("transfer_protocol", ["c-move", "c-get", "dicomweb"])
def test_unpseudonymized_urgent_selective_transfer(
    page: Page, channels_live_server: ChannelsLiveServer, transfer_protocol: str
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, SelectiveTransferJob, "can_process_urgently")
    add_permission(group, SelectiveTransferJob, "can_transfer_unpseudonymized")

    if transfer_protocol == "dicomweb":
        orthancs = setup_dicomweb_orthancs()
    elif transfer_protocol == "c-move":
        orthancs = setup_dimse_orthancs(cget_enabled=False)
    else:
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
@pytest.mark.parametrize("transfer_protocol", ["c-move", "c-get", "dicomweb"])
def test_unpseudonymized_urgent_selective_transfer_and_convert_to_nifti(
    page: Page, channels_live_server: ChannelsLiveServer, transfer_protocol: str
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, SelectiveTransferJob, "can_process_urgently")
    add_permission(group, SelectiveTransferJob, "can_transfer_unpseudonymized")

    if transfer_protocol == "dicomweb":
        orthancs = setup_dicomweb_orthancs()
    elif transfer_protocol == "c-move":
        orthancs = setup_dimse_orthancs(cget_enabled=False)
    else:
        orthancs = setup_dimse_orthancs()

    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Use a temporary directory for the NIfTI output
    with tempfile.TemporaryDirectory() as temp_dir:
        download_folder = DicomFolderFactory.create(name="Downloads", path=temp_dir)
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
        success_message = page.locator(
            "text=Successfully submitted transfer job with ID"
        ).inner_text()
        job_id = int(success_message.split("ID")[-1].strip())

        page.locator('a:has-text("ID")').click()

        run_worker_once()
        page.reload()

        # Validate NIfTI files
        current_date = timezone.now().strftime("%Y%m%d")  # Get the current date dynamically
        expected_folder_name = f"adit_selective_transfer_{job_id}_{current_date}_{user.username}"
        nifti_folder = Path(temp_dir) / expected_folder_name / "1008"

        assert nifti_folder.exists(), f"NIfTI folder '{expected_folder_name}' does not exist."
        nifti_files = list(nifti_folder.glob("**/*.nii*"))
        assert len(nifti_files) > 0, "No NIfTI files were generated."

        # Hardcoded expected filenames
        expected_filenames = [
            "13-t2_ciss3d_tra_iso_0.7.nii.gz",
            "12-SWI_Images.nii.gz",
            "10-DWI_4scan_trace_tra_ADC.nii.gz",
            "1-AAHead_Scout.nii.gz",
            "9-DWI_4scan_trace_tra_TRACEW.nii.gz",
            "5-t2_tse_tra_5mm.nii.gz",
        ]

        # Validate filenames
        actual_filenames = [file.name for file in nifti_files]
        assert Counter(expected_filenames) == Counter(actual_filenames), (
            "NIfTI files do not match expected filenames."
        )

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
def test_unpseudonymized_selective_direct_download_with_dimse_server(
    page: Page, channels_live_server: ChannelsLiveServer
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, "selective_transfer", "can_download_study")

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Modality").click()
    page.get_by_label("Modality").fill("MR")
    page.get_by_label("Modality").press("Enter")
    page.locator('tr:has-text("1003"):has-text("2020") input').click()
    
    link_locator = page.locator('a[href*="download/servers/1/patients/1003"]')
    link_locator.wait_for()

    # Intercept the download and capture it
    with page.expect_download() as download_info:
        link_locator.click()

    download = download_info.value

    # Read file content directly
    path = download.path()
    with open(path, "rb") as f:
        zip_bytes = io.BytesIO(f.read())

    # Inspect zip file contents
    with zipfile.ZipFile(zip_bytes) as zf:
        actual_files = set(zf.namelist())
        expected_files = {
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/1-AAHead_Scout/1.3.12.2.1107.5.2.18.41369.2020070517301070393121257.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/1-AAHead_Scout/1.3.12.2.1107.5.2.18.41369.2020070517301070783621262.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/1-AAHead_Scout/1.3.12.2.1107.5.2.18.41369.2020070517301071809821266.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/1-AAHead_Scout/1.3.12.2.1107.5.2.18.41369.2020070517301076038721300.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/5-t2_tse_tra 5mm/1.3.12.2.1107.5.2.18.41369.2020070517335682449622068.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/5-t2_tse_tra 5mm/1.3.12.2.1107.5.2.18.41369.2020070517335685098622070.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/5-t2_tse_tra 5mm/1.3.12.2.1107.5.2.18.41369.2020070517335752885122121.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/5-t2_tse_tra 5mm/1.3.12.2.1107.5.2.18.41369.2020070517335753271722124.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/8-SWI_Images/1.3.12.2.1107.5.2.18.41369.2020070517415775163724138.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/8-SWI_Images/1.3.12.2.1107.5.2.18.41369.2020070517415775190624139.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/8-SWI_Images/1.3.12.2.1107.5.2.18.41369.2020070517415775215724140.dcm',
            'study_download_1.2.840.113845.11.1000000001951524609.20200705172608.2689471/1003/20200202-172931-MR/8-SWI_Images/1.3.12.2.1107.5.2.18.41369.2020070517415775243224141.dcm',
        }
        assert actual_files == expected_files
