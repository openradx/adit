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

    group.refresh_from_db()

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    user.refresh_from_db()

    server_id = orthancs[0].pk
    patient_id = "1001"
    study_uid = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"
    study_modalities = "CT,SR"
    encoded_study_modalities = "CT%2CSR"
    study_date = "20190604"
    study_time = "182823"

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Patient ID").click()
    page.get_by_label("Patient ID").fill(f"{patient_id}")
    page.get_by_label("Patient ID").press("Enter")

    base_download_link = f"download/servers/{server_id}/patients/{patient_id}/studies/{study_uid}"
    optional_params = (
        f"?study_modalities={encoded_study_modalities}"
        f"&study_date={study_date}"
        f"&study_time={study_time}"
    )
    download_link = base_download_link + optional_params

    link_locator = page.locator(f'a[href*="{download_link}"]')

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
    base_path = (
        f"study_download_{study_uid}/{patient_id}/{study_date}-{study_time}-{study_modalities}"
    )
    with zipfile.ZipFile(zip_bytes) as zf:
        actual_files = set(zf.namelist())
        expected_files = {
            f"{base_path}/999-FUJI Basic Text SR for HL7 Radiological Report/"
            "1.2.840.113845.11.5000000001951524609.20200705191841.1656640.dcm",
            f"{base_path}/2-Kopf nativ  5.0  H42s/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005503.dcm",
            f"{base_path}/2-Kopf nativ  5.0  H42s/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005505.dcm",
            f"{base_path}/2-Kopf nativ  5.0  H42s/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005504.dcm",
            f"{base_path}/2-Kopf nativ  5.0  H42s/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005506.dcm",
            f"{base_path}/3-Kopf nativ  2.0  H70h/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005545.dcm",
            f"{base_path}/3-Kopf nativ  2.0  H70h/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005546.dcm",
            f"{base_path}/3-Kopf nativ  2.0  H70h/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005544.dcm",
            f"{base_path}/3-Kopf nativ  2.0  H70h/"
            "1.3.12.2.1107.5.1.4.66002.30000020070514400054400005543.dcm",
            f"{base_path}/1-Topogramm  0.6  T20f/"
            "1.3.12.2.1107.5.1.4.66002.30000020070513455668000000632.dcm",
            f"{base_path}/1-Topogramm  0.6  T20f/"
            "1.3.12.2.1107.5.1.4.66002.30000020070513455668000000610.dcm",
        }
        assert actual_files == expected_files


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_pseudonymized_selective_direct_download_with_dimse_server(
    page: Page, channels_live_server: ChannelsLiveServer
):
    # Arrange
    user = create_and_login_example_user(page, channels_live_server.url)
    group = create_selective_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, "selective_transfer", "can_download_study")

    group.refresh_from_db()

    orthancs = setup_dimse_orthancs()
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    user.refresh_from_db()

    server_id = orthancs[0].pk
    patient_id = "1001"
    study_uid = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"
    encoded_study_modalities = "CT%2CSR"
    study_date = "20190604"
    study_time = "182823"
    pseudonym = "Test Pseudonym"
    encoded_pseudonym = "Test+Pseudonym"
    included_modalities = "CT"

    # Act
    page.goto(channels_live_server.url + "/selective-transfer/jobs/new/")
    page.get_by_label("Source").select_option(label="DICOM Server Orthanc Test Server 1")
    page.get_by_label("Destination").select_option(label="DICOM Server Orthanc Test Server 2")
    page.get_by_label("Pseudonym").click(force=True)
    page.get_by_label("Pseudonym").fill(f"{pseudonym}")
    page.get_by_label("Patient ID").click()
    page.get_by_label("Patient ID").fill(f"{patient_id}")
    page.get_by_label("Patient ID").press("Enter")

    base_download_link = f"download/servers/{server_id}/patients/{patient_id}/studies/{study_uid}"
    optional_params = (
        f"?pseudonym={encoded_pseudonym}"
        f"&study_modalities={encoded_study_modalities}"
        f"&study_date={study_date}"
        f"&study_time={study_time}"
    )
    download_link = base_download_link + optional_params
    link_locator = page.locator(f'a[href*="{download_link}"]')

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
    base_path = (
        f"study_download_{study_uid}/{pseudonym}/{study_date}-{study_time}-{included_modalities}"
    )
    with zipfile.ZipFile(zip_bytes) as zf:
        file_entries = [name for name in zf.namelist() if not name.endswith("/")]
        expected_series_file_counts = {
            f"{base_path}/2-Kopf nativ  5.0  H42s/": 4,
            f"{base_path}/3-Kopf nativ  2.0  H70h/": 4,
            f"{base_path}/1-Topogramm  0.6  T20f/": 2,
        }
        actual_series_file_counts = {}

        for entry in file_entries:
            assert entry.endswith(".dcm"), f"Unexpected file type in archive: {entry}"
            assert entry.startswith(f"{base_path}/"), (
                f"File {entry} not contained in base path {base_path}"
            )
            series_path = entry.rsplit("/", 1)[0] + "/"
            actual_series_file_counts[series_path] = (
                actual_series_file_counts.get(series_path, 0) + 1
            )

        assert actual_series_file_counts == expected_series_file_counts
