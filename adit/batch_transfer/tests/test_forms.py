from io import StringIO
from unittest.mock import patch, create_autospec
import pytest
from django.core.files import File
from adit.core.factories import DicomServerFactory
from ..forms import BatchTransferJobForm


@pytest.fixture
def data_dict():
    return {
        "source": DicomServerFactory(),
        "destination": DicomServerFactory(),
        "project_name": "Apollo project",
        "project_description": "Fly to the moon",
    }


@pytest.fixture
def file_dict():
    file = create_autospec(File, size=5242880)
    file.name = "sample_sheet.csv"
    file.read.return_value.decode.return_value = ""
    return {"csv_file": file}


def test_field_labels():
    form = BatchTransferJobForm()

    assert len(form.fields) == 8
    assert "source" in form.fields
    assert "destination" in form.fields
    assert form.fields["project_name"].label == "Project name"
    assert form.fields["project_description"].label == "Project description"
    assert form.fields["trial_protocol_id"].label == "Trial protocol ID"
    assert form.fields["trial_protocol_name"].label == "Trial protocol name"
    assert form.fields["csv_file"].label == "CSV file"


@pytest.mark.django_db
@patch("adit.batch_transfer.forms.RequestsParser", autospec=True)
@patch("adit.batch_transfer.forms.chardet.detect", return_value={"encoding": "UTF-8"})
def test_with_valid_data(_, ParserMock, data_dict, file_dict):
    parser_mock = ParserMock.return_value
    parser_mock.parse.return_value = []

    form = BatchTransferJobForm(data_dict, file_dict)

    assert form.is_valid()
    ParserMock.assert_called_once()
    parser_mock.parse.assert_called_once()
    assert isinstance(parser_mock.parse.call_args.args[0], StringIO)


def test_with_missing_values():
    form = BatchTransferJobForm({})

    assert not form.is_valid()
    assert len(form.errors) == 5
    assert form.errors["source"] == ["This field is required."]
    assert form.errors["destination"] == ["This field is required."]
    assert form.errors["project_name"] == ["This field is required."]
    assert form.errors["project_description"] == ["This field is required."]
    assert form.errors["csv_file"] == ["This field is required."]


@pytest.mark.django_db
def test_disallow_too_large_file(data_dict):
    file = create_autospec(File, size=5242881)
    file.name = "sample_sheet.xlsx"

    form = BatchTransferJobForm(data_dict, {"csv_file": file})

    assert not form.is_valid()
    assert "File too large" in form.errors["csv_file"][0]
