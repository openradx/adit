import json

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group

from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.utils.auth_utils import grant_access

from ..forms import MassTransferJobForm


@pytest.mark.django_db
def test_clean_clears_salt_when_pseudonymize_unchecked():
    """When pseudonymize is unchecked, the salt should be cleared."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "should-be-cleared",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["pseudonym_salt"] == ""


@pytest.mark.django_db
def test_clean_keeps_salt_when_pseudonymize_checked():
    """When pseudonymize is checked, the salt should be preserved."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": True,
            "pseudonym_salt": "my-custom-salt",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["pseudonym_salt"] == "my-custom-salt"


@pytest.mark.django_db
def test_clean_allows_empty_salt_with_pseudonymize_for_random_mode():
    """Pseudonymize checked with empty salt = random pseudonyms (no linking)."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": True,
            "pseudonym_salt": "",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["pseudonym_salt"] == ""
    assert form.cleaned_data["pseudonymize"] is True


@pytest.mark.django_db
def test_clean_destination_accepts_server():
    """Server destinations should be accepted."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomServerFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_clean_destination_accepts_folder():
    """Folder destinations should still be accepted (regression guard)."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_clean_clears_nifti_with_server_destination():
    """NIfTI conversion should be silently cleared when destination is a server."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomServerFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "",
            "convert_to_nifti": True,
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["convert_to_nifti"] is False


@pytest.mark.django_db
def test_clean_allows_nifti_with_folder_destination():
    """NIfTI conversion should be allowed when destination is a folder."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "",
            "convert_to_nifti": True,
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
        user=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["convert_to_nifti"] is True
