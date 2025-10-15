import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from adit.core.models import DicomJob, DicomTask

from ..factories import SelectiveTransferJobFactory, SelectiveTransferTaskFactory


@pytest.mark.django_db
class TestSelectiveTransfer:
    def test_selective_transfer_job_list_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)

        response = client.get("/selective-transfer/jobs/")
        assert response.status_code == 200

    def test_selective_transfer_job_create_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="add_selectivetransferjob",
            content_type=ContentType.objects.get(
                app_label="selective_transfer", model="selectivetransferjob"
            ),
        )
        user.user_permissions.add(permission)
        client.force_login(user)

        response = client.get("/selective-transfer/jobs/new/")
        assert response.status_code == 200

    def test_selective_transfer_job_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        client.force_login(user)

        response = client.get(f"/selective-transfer/jobs/{job.pk}/")
        assert response.status_code == 200

    def test_selective_transfer_job_verify_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.UNVERIFIED)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/verify/")
        assert response.status_code == 302

    def test_selective_transfer_job_cancel_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/cancel/")
        assert response.status_code == 302

    def test_selective_transfer_job_resume_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.CANCELED)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/resume/")
        assert response.status_code == 302

    def test_selective_transfer_job_retry_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/retry/")
        assert response.status_code == 302

    def test_selective_transfer_job_restart_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/restart/")
        assert response.status_code == 302

    def test_selective_transfer_task_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        task = SelectiveTransferTaskFactory.create(job=job)
        client.force_login(user)

        response = client.get(f"/selective-transfer/tasks/{task.pk}/")
        assert response.status_code == 200

    def test_selective_transfer_job_delete_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/delete/")
        assert response.status_code == 302

    def test_selective_transfer_task_delete_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        job.tasks.all().delete()
        task_to_delete = SelectiveTransferTaskFactory.create(
            job=job, status=DicomTask.Status.PENDING
        )

        client.force_login(user)

        response = client.post(f"/selective-transfer/tasks/{task_to_delete.pk}/delete/")
        assert response.status_code == 302

    def test_selective_transfer_task_reset_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)

        task = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/selective-transfer/tasks/{task.pk}/reset/")
        assert response.status_code == 302

    def test_selective_transfer_task_kill_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        task = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.IN_PROGRESS)
        client.force_login(user)

        response = client.post(f"/selective-transfer/tasks/{task.pk}/kill/")
        assert response.status_code == 302
