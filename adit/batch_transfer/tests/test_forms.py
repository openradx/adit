from unittest.mock import create_autospec, patch

import pytest
from django.core.files import File

from adit.core.factories import DicomServerFactory
from shared.accounts.factories import UserFactory
from shared.accounts.models import User

from ..forms import BatchTransferJobForm


@pytest.fixture
def data_dict():
    return {
        "source": DicomServerFactory(),
        "destination": DicomServerFactory(),
        "project_name": "Apollo project",
        "project_description": "Fly to the moon",
        "ethics_application_id": "12345",
    }


@pytest.fixture
def file_dict():
    file = create_autospec(File, size=5242880)
    file.name = "sample_sheet.xlsx"
    file.read.return_value.decode.return_value = ""
    return {"batch_file": file}


def test_field_labels():
    # Arrange
    user = create_autospec(User)
    user.has_perm.return_value = True

    # Act
    form = BatchTransferJobForm(user=user)

    # Assert
    assert len(form.fields) == 10
    assert "source" in form.fields
    assert "destination" in form.fields
    assert "urgent" in form.fields
    assert form.fields["project_name"].label == "Project name"
    assert form.fields["project_description"].label == "Project description"
    assert form.fields["trial_protocol_id"].label == "Trial ID"
    assert form.fields["trial_protocol_name"].label == "Trial name"
    assert form.fields["ethics_application_id"].label == "Ethics committee approval"
    assert form.fields["batch_file"].label == "Batch file"


@pytest.mark.django_db
@patch("adit.batch_transfer.forms.BatchTransferFileParser.parse", autospec=True)
def test_with_valid_data(parse_mock, grant_access, data_dict, file_dict):
    # Arrange
    user = UserFactory.create()
    grant_access(user, data_dict["source"], "source")
    grant_access(user, data_dict["destination"], "destination")
    parse_mock.return_value = []

    # Act
    form = BatchTransferJobForm(data_dict, file_dict, user=user)

    # Assert
    assert form.is_valid()
    parse_mock.assert_called_once()
    assert parse_mock.call_args.args[1] == file_dict["batch_file"]


def test_with_missing_values():
    # Arrange
    user = create_autospec(User)
    user.has_perm.return_value = True

    # Act
    form = BatchTransferJobForm({}, user=user)

    # Assert
    assert not form.is_valid()
    assert len(form.errors) == 6
    assert form.errors["source"] == ["This field is required."]
    assert form.errors["destination"] == ["This field is required."]
    assert form.errors["project_name"] == ["This field is required."]
    assert form.errors["project_description"] == ["This field is required."]
    assert form.errors["ethics_application_id"] == ["This field is required."]
    assert form.errors["batch_file"] == ["This field is required."]


@pytest.mark.django_db
def test_disallow_too_large_file(data_dict):
    # Arrange
    file = create_autospec(File, size=5242881)
    file.name = "sample_sheet.xlsx"
    user = create_autospec(User)
    user.has_perm.return_value = True

    # Act
    form = BatchTransferJobForm(data_dict, {"batch_file": file}, user=user)

    # Assert
    assert not form.is_valid()
    assert "File too large" in form.errors["batch_file"][0]
