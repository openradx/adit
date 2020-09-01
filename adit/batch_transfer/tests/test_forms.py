from io import StringIO
from unittest.mock import patch, create_autospec
from django.test import TestCase
from django.core.files import File
from adit.main.factories import DicomServerFactory
from adit.accounts.models import User
from ..forms import BatchTransferJobForm


class BatchTransferJobFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data_dict = {
            "source": DicomServerFactory(),
            "destination": DicomServerFactory(),
            "project_name": "Apollo project",
            "project_description": "Fly to the moon",
        }

        file = create_autospec(File, size=5242880)
        file.name = "sample_sheet.csv"
        file.read.return_value.decode.return_value = ""
        cls.file_dict = {"csv_file": file}

        cls.user = create_autospec(User)

    def test_field_labels(self):
        form = BatchTransferJobForm()
        self.assertEqual(len(form.fields), 8)
        self.assertEqual(form.fields["source"].label, "Source")
        self.assertEqual(form.fields["destination"].label, "Destination")
        self.assertEqual(form.fields["project_name"].label, "Project name")
        self.assertEqual(
            form.fields["project_description"].label, "Project description"
        )
        self.assertEqual(form.fields["trial_protocol_id"].label, "Trial protocol id")
        self.assertEqual(
            form.fields["trial_protocol_name"].label, "Trial protocol name"
        )
        self.assertEqual(form.fields["archive_password"].label, "Archive password")
        self.assertEqual(form.fields["csv_file"].label, "CSV file")

    @patch("adit.batch_transfer.forms.RequestParser", autospec=True)
    @patch(
        "adit.batch_transfer.forms.chardet.detect", return_value={"encoding": "UTF-8"}
    )
    def test_with_valid_data(self, _, ParserMock):
        parser_mock = ParserMock.return_value
        parser_mock.parse.return_value = []

        form = BatchTransferJobForm(self.data_dict, self.file_dict)
        self.assertTrue(form.is_valid())
        ParserMock.assert_called_once()
        parser_mock.parse.assert_called_once()
        self.assertIsInstance(parser_mock.parse.call_args.args[0], StringIO)

    def test_with_missing_values(self):
        form = BatchTransferJobForm({})
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 5)
        self.assertEqual(form.errors["source"], ["This field is required."])
        self.assertEqual(form.errors["destination"], ["This field is required."])
        self.assertEqual(form.errors["project_name"], ["This field is required."])
        self.assertEqual(
            form.errors["project_description"], ["This field is required."]
        )
        self.assertEqual(form.errors["csv_file"], ["This field is required."])

    def test_disallow_too_large_file(self):
        file = create_autospec(File, size=5242881)
        file.name = "sample_sheet.xlsx"
        form = BatchTransferJobForm(self.data_dict, {"csv_file": file})
        self.assertFalse(form.is_valid())
        self.assertIn("File too large", form.errors["csv_file"][0])
