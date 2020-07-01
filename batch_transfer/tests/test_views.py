from django.test import TestCase
from django.conf import settings
import os
from django.contrib.auth.models import Group
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.factories import UserFactory
from main.factories import DicomServerFactory
from ..models import BatchTransferJob

class BatchTransferJobCreateTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Setup test users
        cls.user_without_permission = UserFactory()

        cls.user_with_permission = UserFactory()
        batch_transferrers_group = Group.objects.get(name='batch_transferrers')
        cls.user_with_permission.groups.add(batch_transferrers_group)

        samples_folder = os.path.join(settings.BASE_DIR, '_debug', 'samples')

        # Real excel file
        def load_file(filename):
            file_path = os.path.join(samples_folder, filename)
            file_content = open(file_path, 'rb').read()
            return SimpleUploadedFile(
                name=filename,
                content=file_content,
                content_type='application/vnd.ms-excel'
            )

        cls.form_data = {
            'source': DicomServerFactory().id,
            'destination': DicomServerFactory().id,
            'project_name': 'Apollo project',
            'project_description': 'Fly to the moon',
            'excel_file': load_file('sample_sheet_valid_small.xlsx')
        }

    def test_user_must_be_logged_in_to_access_view(self):
        response = self.client.get(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 302)

    def test_user_must_have_permission_to_access_view(self):
        self.client.force_login(self.user_without_permission)
        response = self.client.get(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_user_with_permission_can_access_form(self):
        self.client.force_login(self.user_with_permission)
        response = self.client.get(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'batch_transfer/batch_transfer_job_form.html')

    def test_job_can_be_created_successfully(self):
        self.client.force_login(self.user_with_permission)
        response = self.client.post(reverse('new_batch_transfer_job'), self.form_data)
        job = BatchTransferJob.objects.first()
        self.assertEqual(job.items.count(), 3)

    def test_job_cant_be_created_with_missing_fields(self):
        self.client.force_login(self.user_with_permission)
        for key_to_exclude in self.form_data:
            invalid_form_data = self.form_data.copy()
            del invalid_form_data[key_to_exclude]
            response = self.client.post(reverse('new_batch_transfer_job'), invalid_form_data)
            self.assertGreater(len(response.context['form'].errors), 0)
            self.assertIsNone(BatchTransferJob.objects.first())