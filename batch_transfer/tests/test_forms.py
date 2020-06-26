import os
from django.test import TestCase
from unittest.mock import MagicMock
from django.core.files import File
from main.factories import DicomServerFactory
from ..forms import BatchTransferJobForm

class BatchTransferJobFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.server1 = DicomServerFactory()
        cls.server2 = DicomServerFactory()

        cls.excel_file_mock = file_mock = MagicMock(spec=File, name='FileMock')
        cls.excel_file_mock.name = 'sample_sheet.xlsx'

    def test_batch_form_field_labels(self):
        form = BatchTransferJobForm()
        self.assertEqual(len(form.fields), 8)
        self.assertEqual(form.fields['source'].label, 'Source')
        self.assertEqual(form.fields['destination'].label, 'Destination')
        self.assertEqual(form.fields['project_name'].label, 'Project name')
        self.assertEqual(form.fields['project_description'].label, 'Project description')
        self.assertEqual(form.fields['pseudonymize'].label, 'Pseudonymize')
        self.assertEqual(form.fields['trial_protocol_id'].label, 'Trial protocol id')
        self.assertEqual(form.fields['trial_protocol_name'].label, 'Trial protocol name')
        self.assertIsNone(form.fields['excel_file'].label)

    def test_batch_form_with_valid_data(self):
        data = {
            'source': self.server1,
            'destination': self.server2,
            'project_name': 'Apollo project',
            'project_description': 'Fly to the moon'
        }
        file_dict = { 'excel_file': self.excel_file_mock }
        form = BatchTransferJobForm(data, file_dict)
        self.assertTrue(form.is_valid())

    def test_batch_form_with_missing_values(self):
        form = BatchTransferJobForm({})
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 5)
        self.assertEqual(form.errors['source'], ['This field is required.'])
        self.assertEqual(form.errors['destination'], ['This field is required.'])
        self.assertEqual(form.errors['project_name'], ['This field is required.'])
        self.assertEqual(form.errors['project_description'], ['This field is required.'])
        self.assertEqual(form.errors['excel_file'], ['This field is required.'])
        