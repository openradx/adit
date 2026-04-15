import json
import tempfile
from pathlib import Path

import nibabel as nib
import pytest
from adit_radis_shared.common.utils.testing_helpers import (
    add_permission,
    add_user_to_group,
    create_and_login_example_user,
    run_worker_once,
)
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from adit.core.factories import DicomFolderFactory
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.testing_helpers import setup_dicomweb_orthancs, setup_dimse_orthancs
from adit.mass_transfer.models import MassTransferJob
from adit.mass_transfer.utils.testing_helpers import create_mass_transfer_group

FILTERS_CT_ONLY = json.dumps([{"modality": "CT"}])


def _fill_mass_transfer_form(
    page: Page,
    *,
    source_label: str = "DICOM Server Orthanc Test Server 1",
    destination_label: str = "DICOM Server Orthanc Test Server 2",
    start_date: str = "2018-08-20",
    end_date: str = "2018-08-20",
    pseudonymize: bool = True,
    convert_to_nifti: bool = False,
    filters_json: str = FILTERS_CT_ONLY,
):
    page.get_by_label("Source").select_option(label=source_label)
    page.get_by_label("Destination").select_option(label=destination_label)
    page.get_by_label("Start date").fill(start_date)
    page.get_by_label("End date").fill(end_date)

    pseudonymize_checkbox = page.get_by_label("Pseudonymize")
    if pseudonymize and not pseudonymize_checkbox.is_checked():
        pseudonymize_checkbox.click(force=True)
    elif not pseudonymize and pseudonymize_checkbox.is_checked():
        pseudonymize_checkbox.click(force=True)

    if convert_to_nifti:
        page.get_by_label("Convert to NIfTI").click(force=True)

    # Set filters in CodeMirror editor
    page.evaluate(
        """(value) => {
            const cm = document.querySelector('.CodeMirror').CodeMirror;
            cm.setValue(value);
        }""",
        filters_json,
    )

    page.locator('input:has-text("Create Job")').click()


def _run_mass_transfer_workers():
    # First run: processes queue_mass_transfer_tasks on default queue
    run_worker_once()
    # Second run: processes process_mass_transfer_task on mass_transfer queue
    run_worker_once()


def _setup_orthancs(transfer_protocol: str):
    if transfer_protocol == "dicomweb":
        return setup_dicomweb_orthancs()
    elif transfer_protocol == "c-move":
        return setup_dimse_orthancs(cget_enabled=False)
    else:
        return setup_dimse_orthancs()


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("transfer_protocol", ["c-move", "c-get", "dicomweb"])
def test_unpseudonymized_mass_transfer_to_server(
    page: Page, live_server: LiveServer, transfer_protocol: str
):
    user = create_and_login_example_user(page, live_server.url)
    group = create_mass_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, MassTransferJob, "can_transfer_unpseudonymized")

    orthancs = _setup_orthancs(transfer_protocol)
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    page.goto(live_server.url + "/mass-transfer/jobs/new/")
    _fill_mass_transfer_form(page, pseudonymize=False)

    _run_mass_transfer_workers()
    page.reload()

    expect(page.locator('dl:has-text("Success")')).to_be_visible()


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("transfer_protocol", ["c-move", "c-get", "dicomweb"])
def test_pseudonymized_mass_transfer_to_server(
    page: Page, live_server: LiveServer, transfer_protocol: str
):
    user = create_and_login_example_user(page, live_server.url)
    group = create_mass_transfer_group()
    add_user_to_group(user, group)

    orthancs = _setup_orthancs(transfer_protocol)
    grant_access(group, orthancs[0], source=True)
    grant_access(group, orthancs[1], destination=True)

    page.goto(live_server.url + "/mass-transfer/jobs/new/")
    _fill_mass_transfer_form(page, pseudonymize=True)

    _run_mass_transfer_workers()
    page.reload()

    expect(page.locator('dl:has-text("Success")')).to_be_visible()


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("transfer_protocol", ["c-move", "c-get", "dicomweb"])
def test_mass_transfer_to_folder(
    page: Page, live_server: LiveServer, transfer_protocol: str
):
    user = create_and_login_example_user(page, live_server.url)
    group = create_mass_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, MassTransferJob, "can_transfer_unpseudonymized")

    orthancs = _setup_orthancs(transfer_protocol)
    grant_access(group, orthancs[0], source=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        download_folder = DicomFolderFactory.create(name="Downloads", path=temp_dir)
        grant_access(group, download_folder, destination=True)

        page.goto(live_server.url + "/mass-transfer/jobs/new/")
        _fill_mass_transfer_form(
            page,
            destination_label="DICOM Folder Downloads",
            pseudonymize=False,
        )

        _run_mass_transfer_workers()
        page.reload()

        expect(page.locator('dl:has-text("Success")')).to_be_visible()

        # Verify DICOM files were written to disk
        dcm_files = list(Path(temp_dir).glob("**/*.dcm"))
        assert len(dcm_files) > 0, "No DICOM files were written to the output folder."


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("transfer_protocol", ["c-move", "c-get", "dicomweb"])
def test_mass_transfer_to_folder_with_nifti_conversion(
    page: Page, live_server: LiveServer, transfer_protocol: str
):
    user = create_and_login_example_user(page, live_server.url)
    group = create_mass_transfer_group()
    add_user_to_group(user, group)
    add_permission(group, MassTransferJob, "can_transfer_unpseudonymized")

    orthancs = _setup_orthancs(transfer_protocol)
    grant_access(group, orthancs[0], source=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        download_folder = DicomFolderFactory.create(name="Downloads", path=temp_dir)
        grant_access(group, download_folder, destination=True)

        page.goto(live_server.url + "/mass-transfer/jobs/new/")
        _fill_mass_transfer_form(
            page,
            destination_label="DICOM Folder Downloads",
            pseudonymize=False,
            convert_to_nifti=True,
        )

        _run_mass_transfer_workers()
        page.reload()

        expect(page.locator('dl:has-text("Success")')).to_be_visible()

        # Verify NIfTI files were generated
        nifti_files = list(Path(temp_dir).glob("**/*.nii*"))
        assert len(nifti_files) > 0, "No NIfTI files were generated."

        for nifti_file in nifti_files:
            img = nib.load(nifti_file)  # type: ignore
            assert img is not None, f"Invalid NIfTI file: {nifti_file}"
