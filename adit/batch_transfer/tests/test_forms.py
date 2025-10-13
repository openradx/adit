import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from django.core.files import File
from pytest_mock import MockerFixture

from adit.batch_transfer.forms import BatchTransferJobForm
from adit.batch_transfer.utils.testing_helpers import (
    create_batch_transfer_group,
    create_data_dict,
    create_file_dict,
)
from adit.core.utils.auth_utils import grant_access


@pytest.mark.django_db
def test_field_labels(mocker: MockerFixture):
    # Arrange
    user = UserFactory.create()
    mocker.patch.object(user, "has_perm", return_value=True)

    # Act
    form = BatchTransferJobForm(user=user)

    # Assert
    assert len(form.fields) == 11
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
def test_with_valid_data(mocker: MockerFixture):
    # Arrange
    user = UserFactory.create()
    group = create_batch_transfer_group()
    add_user_to_group(user, group)
    data_dict = create_data_dict()
    grant_access(group, data_dict["source"], source=True)
    grant_access(group, data_dict["destination"], destination=True)
    parse_mock = mocker.patch(
        "adit.batch_transfer.forms.BatchTransferFileParser.parse", autospec=True
    )
    parse_mock.return_value = []
    file_dict = create_file_dict()

    # Act
    form = BatchTransferJobForm(data_dict, file_dict, user=user)

    # Assert
    assert form.is_valid()
    parse_mock.assert_called_once()
    assert parse_mock.call_args.args[1] == file_dict["batch_file"]


@pytest.mark.django_db
def test_with_missing_values(mocker: MockerFixture):
    # Arrange
    user = UserFactory.create()
    mocker.patch.object(user, "has_perm", return_value=True)

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
def test_disallow_too_large_file(mocker: MockerFixture):
    # Arrange
    file = mocker.create_autospec(File, size=5242881)
    file.name = "sample_sheet.xlsx"

    user = UserFactory.create()
    mocker.patch.object(user, "has_perm", return_value=True)

    data_dict = create_data_dict()

    # Act
    form = BatchTransferJobForm(data_dict, {"batch_file": file}, user=user)

    # Assert
    assert not form.is_valid()
    assert "File too large" in form.errors["batch_file"][0]
