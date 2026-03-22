import json

import pytest
from adit_radis_shared.accounts.factories import UserFactory

from adit.core.factories import DicomFolderFactory, DicomServerFactory

from ..forms import MassTransferJobForm


@pytest.mark.django_db
def test_clean_clears_salt_when_pseudonymize_unchecked():
    """When pseudonymize is unchecked, the salt should be cleared."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()

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
