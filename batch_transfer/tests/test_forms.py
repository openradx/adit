from django.test import TestCase
import os
from unittest.mock import MagicMock, patch
from django.core.files import File
from main.factories import DicomServerFactory
from ..forms import BatchTransferJobForm
from accounts.models import User

class BatchTransferJobFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data_dict = {
            'source': DicomServerFactory(),
            'destination': DicomServerFactory(),
            'project_name': 'Apollo project',
            'project_description': 'Fly to the moon'
        }

        file = MagicMock(spec=File, name='FileMock', size=5242880)
        file.name = 'sample_sheet.xlsx'
        cls.file_dict = { 'excel_file': file }

        cls.user = MagicMock(spec=User, name='UserMock')

    def test_field_labels(self):
        form = BatchTransferJobForm(user=self.user)
        self.assertEqual(len(form.fields), 8)
        self.assertEqual(form.fields['source'].label, 'Source')
        self.assertEqual(form.fields['destination'].label, 'Destination')
        self.assertEqual(form.fields['project_name'].label, 'Project name')
        self.assertEqual(form.fields['project_description'].label, 'Project description')
        self.assertEqual(form.fields['pseudonymize'].label, 'Pseudonymize')
        self.assertEqual(form.fields['trial_protocol_id'].label, 'Trial protocol id')
        self.assertEqual(form.fields['trial_protocol_name'].label, 'Trial protocol name')
        self.assertIsNone(form.fields['excel_file'].label)

    @patch('batch_transfer.forms.ExcelProcessor')
    def test_with_valid_data(self, ExcelProcessorMock):
        excel_processer_mock = ExcelProcessorMock.return_value
        excel_processer_mock.extract_data.return_value = []

        form = BatchTransferJobForm(self.data_dict, self.file_dict, user=self.user)
        
        self.assertTrue(form.is_valid())
        ExcelProcessorMock.assert_called_once_with(self.file_dict['excel_file'])
        excel_processer_mock.extract_data.assert_called_once()

    def test_with_missing_values(self):
        form = BatchTransferJobForm({}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 5)
        self.assertEqual(form.errors['source'], ['This field is required.'])
        self.assertEqual(form.errors['destination'], ['This field is required.'])
        self.assertEqual(form.errors['project_name'], ['This field is required.'])
        self.assertEqual(form.errors['project_description'], ['This field is required.'])
        self.assertEqual(form.errors['excel_file'], ['This field is required.'])

    def test_disallow_too_large_file(self):
        file = MagicMock(spec=File, name='FileMock', size=5242881)
        file.name = 'sample_sheet.xlsx'
        form = BatchTransferJobForm(self.data_dict, { 'excel_file': file }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['excel_file'],
                ['File too large. Please keep filesize under 5.0\xa0MB.'])