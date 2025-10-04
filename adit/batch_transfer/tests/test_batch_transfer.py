import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from adit.batch_transfer.factories import BatchTransferJobFactory, BatchTransferTaskFactory
from adit.batch_transfer.models import BatchTransferJob, BatchTransferTask


@pytest.mark.django_db
class TestBatchTransfer:
    def test_batch_transfer_job_list_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        response = client.get("/batch-transfer/jobs/")
        assert response.status_code == 200

    def test_batch_transfer_job_create_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="add_batchtransferjob",
            content_type=ContentType.objects.get_for_model(BatchTransferJob),
        )
        client.force_login(user)
        user.user_permissions.add(permission)
        response = client.post("/batch-transfer/jobs/new/")

        assert response.status_code == 200

    def test_batch_transfer_job_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user)
        response = client.get(f"/batch-transfer/jobs/{job.pk}/")
        assert response.status_code == 200

    def test_batch_transfer_job_delete_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.PENDING)
        response = client.post(f"/batch-transfer/jobs/{job.pk}/delete/")
        assert response.status_code == 302

    def test_batch_transfer_job_verify_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.UNVERIFIED)
        response = client.post(f"/batch-transfer/jobs/{job.pk}/verify/")
        assert response.status_code == 302

    def test_batch_transfer_job_cancel_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.PENDING)
        response = client.post(f"/batch-transfer/jobs/{job.pk}/cancel/")
        assert response.status_code == 302

    def test_batch_transfer_job_restart_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.FAILURE)
        response = client.post(f"/batch-transfer/jobs/{job.pk}/restart/")
        assert response.status_code == 302

    def test_batch_transfer_update_preferences_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        response = client.post("/batch-transfer/update-preferences/")
        assert response.status_code == 200

    def test_batch_transfer_help_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        response = client.get("/batch-transfer/help/", HTTP_HX_REQUEST="true")
        assert response.status_code == 200

    def test_batch_transfer_job_resume_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.CANCELED)
        response = client.post(f"/batch-transfer/jobs/{job.pk}/resume/")
        assert response.status_code == 302

    def test_batch_transfer_job_retry_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.FAILURE)
        response = client.post(f"/batch-transfer/jobs/{job.pk}/retry/")
        assert response.status_code == 302

    def test_batch_transfer_task_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user)
        task = BatchTransferTaskFactory.create(job=job)
        response = client.get(f"/batch-transfer/tasks/{task.pk}/")
        assert response.status_code == 200

    def test_batch_transfer_task_delete_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user)
        task_to_delete = BatchTransferTaskFactory.create(
            job=job, status=BatchTransferTask.Status.PENDING
        )

        response = client.post(f"/batch-transfer/tasks/{task_to_delete.pk}/delete/")
        assert response.status_code == 302

    def test_batch_transfer_task_reset_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user)
        task = BatchTransferTaskFactory.create(job=job, status=BatchTransferTask.Status.FAILURE)
        response = client.post(f"/batch-transfer/tasks/{task.pk}/reset/")
        assert response.status_code == 302

    def test_batch_transfer_task_kill_view(self):
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        client.force_login(user)
        job = BatchTransferJobFactory.create(owner=user)
        task = BatchTransferTaskFactory.create(job=job, status=BatchTransferTask.Status.IN_PROGRESS)
        response = client.post(f"/batch-transfer/tasks/{task.pk}/kill/")
        assert response.status_code == 302
