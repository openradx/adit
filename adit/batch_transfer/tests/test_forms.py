from io import StringIO
from unittest.mock import patch, create_autospec
import pytest
from django.core.files import File
from adit.core.factories import DicomServerFactory
from adit.accounts.models import User
from ..forms import BatchTransferJobForm


@pytest.fixture
def data_dict():
    return {
        "source": DicomServerFactory(),
        "destination": DicomServerFactory(),
        "project_name": "Apollo project",
        "project_description": "Fly to the moon",
        "ethics_committee_approval": "on",
    }


@pytest.fixture
def file_dict():
    file = create_autospec(File, size=5242880)
    file.name = "sample_sheet.csv"
    file.read.return_value.decode.return_value = ""
    return {"csv_file": file}


def test_field_labels():
    # Arrange
    user = create_autospec(User)
    user.has_perm.return_value = True

    # Act
    form = BatchTransferJobForm(user=user)

    # Assert
    assert len(form.fields) == 9
    assert "source" in form.fields
    assert "destination" in form.fields
    assert "urgent" in form.fields
    assert form.fields["project_name"].label == "Project name"
    assert form.fields["project_description"].label == "Project description"
    assert form.fields["trial_protocol_id"].label == "Trial ID"
    assert form.fields["trial_protocol_name"].label == "Trial name"
    assert "ethics_committee_approval" in form.fields
    assert form.fields["csv_file"].label == "CSV file"


@pytest.mark.django_db
@patch("adit.batch_transfer.forms.BatchTransferFileParser.parse", autospec=True)
@patch("adit.batch_transfer.forms.chardet.detect", return_value={"encoding": "UTF-8"})
def test_with_valid_data(_, mock_parse, data_dict, file_dict):
    # Arrange
    mock_parse.return_value = []
    user = create_autospec(User)
    user.has_perm.return_value = True

    # Act
    form = BatchTransferJobForm(data_dict, file_dict, user=user)

    # Assert
    assert form.is_valid()
    mock_parse.assert_called_once()
    assert isinstance(mock_parse.call_args.args[1], StringIO)


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
    assert form.errors["ethics_committee_approval"] == ["This field is required."]
    assert form.errors["csv_file"] == ["This field is required."]


@pytest.mark.django_db
def test_disallow_too_large_file(data_dict):
    # Arrange
    file = create_autospec(File, size=5242881)
    file.name = "sample_sheet.xlsx"
    user = create_autospec(User)
    user.has_perm.return_value = True

    # Act
    form = BatchTransferJobForm(data_dict, {"csv_file": file}, user=user)

    # Assert
    assert not form.is_valid()
    assert "File too large" in form.errors["csv_file"][0]
