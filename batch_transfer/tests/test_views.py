import os
from django.test import TestCase
from django.contrib.auth.models import Group
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.factories import UserFactory

class BatchTransferJobCreateTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Setup test users
        cls.user_without_permission = UserFactory()

        cls.user_with_permission = UserFactory()
        batch_transferrers_group = Group.objects.get(name='batch_transferrers')
        cls.user_with_permission.groups.add(batch_transferrers_group)

        # Use real excel file
        resources_path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'resources')

        def load_file(filename):
            file_path = os.path.join(resources_path, filename)
            file_content = open(file_path, 'rb').read()
            return SimpleUploadedFile(
                name=filename,
                content=file_content,
                content_type='application/vnd.ms-excel'
            )

        cls.excel_file_valid = load_file('sample_sheet_valid.xlsx')

    def test_must_be_logged_in_to_create_batch_job(self):
        response = self.client.get(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 302)

    def test_user_must_have_permission_to_create_batch_job(self):
        self.client.force_login(self.user_without_permission)
        response = self.client.get(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 403)

    def test_with_permission_to_create_batch_job(self):
        self.client.force_login(self.user_with_permission)
        response = self.client.get(reverse('new_batch_transfer_job'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'batch_transfer/batch_transfer_job_form.html')
