import json

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group

from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.utils.auth_utils import grant_access

from ..forms import MassTransferJobForm


@pytest.fixture
def form_env():
    """Create a user, source server, destination folder, and grant access."""
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)
    return {"user": user, "source": source, "destination": destination}


def _make_form(form_env, **overrides):
    """Build a MassTransferJobForm with sensible defaults, applying overrides."""
    data = {
        "source": form_env["source"].pk,
        "destination": form_env["destination"].pk,
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "partition_granularity": "daily",
        "pseudonymize": False,
        "pseudonym_salt": "",
        "filters_json": json.dumps([{"modality": "CT"}]),
    }
    data.update(overrides)
    return MassTransferJobForm(data=data, user=form_env["user"])


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


# --- clean_filters_json tests ---


@pytest.mark.django_db
def test_clean_filters_json_invalid_json(form_env):
    form = _make_form(form_env, filters_json="{not valid json")
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_non_array(form_env):
    form = _make_form(form_env, filters_json=json.dumps({"modality": "CT"}))
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_empty_array(form_env):
    form = _make_form(form_env, filters_json=json.dumps([]))
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_non_dict_item(form_env):
    form = _make_form(form_env, filters_json=json.dumps(["not a dict"]))
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_negative_age(form_env):
    form = _make_form(form_env, filters_json=json.dumps([{"min_age": -5}]))
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_inverted_age_range(form_env):
    form = _make_form(form_env, filters_json=json.dumps([{"min_age": 90, "max_age": 18}]))
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_extra_fields(form_env):
    form = _make_form(
        form_env, filters_json=json.dumps([{"modality": "CT", "unknown_field": "x"}])
    )
    assert not form.is_valid()
    assert "filters_json" in form.errors


# --- clean / clean_source validation tests ---


@pytest.mark.django_db
def test_clean_rejects_end_date_before_start_date(form_env):
    form = _make_form(form_env, start_date="2024-06-01", end_date="2024-01-01")
    assert not form.is_valid()
    assert "__all__" in form.errors


@pytest.mark.django_db
def test_clean_source_rejects_folder():
    user = UserFactory.create()
    source_folder = DicomFolderFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    grant_access(group, source_folder, source=True)
    grant_access(group, destination, destination=True)

    form = MassTransferJobForm(
        data={
            "source": source_folder.pk,
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
    assert not form.is_valid()
    assert "source" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_min_instances_valid(form_env):
    form = _make_form(
        form_env,
        filters_json=json.dumps([{"modality": "CT", "min_number_of_series_related_instances": 5}]),
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_clean_filters_json_min_instances_zero_rejected(form_env):
    form = _make_form(
        form_env,
        filters_json=json.dumps([{"modality": "CT", "min_number_of_series_related_instances": 0}]),
    )
    assert not form.is_valid()
    assert "filters_json" in form.errors


@pytest.mark.django_db
def test_clean_filters_json_min_instances_null_accepted(form_env):
    form = _make_form(
        form_env,
        filters_json=json.dumps(
            [{"modality": "CT", "min_number_of_series_related_instances": None}]
        ),
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_clean_filters_json_min_instances_omitted_accepted(form_env):
    form = _make_form(form_env, filters_json=json.dumps([{"modality": "CT"}]))
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_clean_source_rejects_unauthorized_server():
    user = UserFactory.create()
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    # Only grant destination access, not source
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
    assert not form.is_valid()
    assert "source" in form.errors
