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
        """
        Test that a logged-in user can successfully access the job list view.

        Arrange: Create an active user.
        Act: Log in the user and make a GET request to the job list URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)

        response = client.get("/selective-transfer/jobs/")
        assert response.status_code == 200

    def test_selective_transfer_job_create_view(self):
        """
        Test that a user with the correct permission can access the job creation page.

        Arrange: Create an active user and give them the 'add_selectivetransferjob'
                 permission.
        Act: Log in the user and make a GET request to the new job URL.
        Assert: The response status code is 200 (OK).
        """
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
        """
        Test that a logged-in user can view the detail page of a specific job.

        Arrange: Create an active user and a job owned by that user.
        Act: Log in the user and make a GET request to the job's detail URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        client.force_login(user)

        response = client.get(f"/selective-transfer/jobs/{job.pk}/")
        assert response.status_code == 200

    def test_selective_transfer_job_verify_view(self):
        """
        Test that a staff user can successfully verify an unverified job.

        Arrange: Create an active staff user and an unverified job.
        Act: Log in the user and make a POST request to the job's verify URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.UNVERIFIED)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/verify/")
        assert response.status_code == 302

    def test_selective_transfer_job_cancel_view(self):
        """
        Test that a user can successfully cancel a pending job.

        Arrange: Create an active user and a pending job.
        Act: Log in the user and make a POST request to the job's cancel URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/cancel/")
        assert response.status_code == 302

    def test_selective_transfer_job_resume_view(self):
        """
        Test that a user can successfully resume a canceled job.

        Arrange: Create an active user and a canceled job.
        Act: Log in the user and make a POST request to the job's resume URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.CANCELED)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/resume/")
        assert response.status_code == 302

    def test_selective_transfer_job_retry_view(self):
        """
        Test that a user can successfully retry a failed job.

        Arrange: Create an active user and a failed job.
        Act: Log in the user and make a POST request to the job's retry URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/retry/")
        assert response.status_code == 302

    def test_selective_transfer_job_restart_view(self):
        """
        Test that a staff user can successfully restart a failed job.

        Arrange: Create an active staff user and a failed job.
        Act: Log in the user and make a POST request to the job's restart URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/restart/")
        assert response.status_code == 302

    def test_selective_transfer_task_detail_view(self):
        """
        Test that a logged-in user can view the detail page of a specific task.

        Arrange: Create an active user, a job, and a task belonging to that job.
        Act: Log in the user and make a GET request to the task's detail URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        task = SelectiveTransferTaskFactory.create(job=job)
        client.force_login(user)

        response = client.get(f"/selective-transfer/tasks/{task.pk}/")
        assert response.status_code == 200

    def test_selective_transfer_job_delete_view(self):
        """
        Test that a user can successfully delete a job when business rules allow it.

        Jobs can only be deleted if they have UNVERIFIED or PENDING status
        AND have no non-pending tasks.

        Arrange: Create an active user and a job with PENDING status.
        Act: Log in the user and make a POST request to the job's delete URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
        client.force_login(user)

        response = client.post(f"/selective-transfer/jobs/{job.pk}/delete/")
        assert response.status_code == 302

    def test_selective_transfer_task_delete_view(self):
        """
        Test that a user can successfully delete a task when business rules allow it.

        Tasks can only be deleted if they have PENDING status.

        Arrange: Create an active user, a job, and a task with PENDING status.
        Act: Log in the user and make a POST request to the task's delete URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        job.tasks.all().delete()
        task_to_delete = SelectiveTransferTaskFactory.create(
            job=job, status=DicomTask.Status.PENDING
        )
        remaining_task = SelectiveTransferTaskFactory.create(
            job=job, status=DicomTask.Status.SUCCESS
        )

        client.force_login(user)

        response = client.post(f"/selective-transfer/tasks/{task_to_delete.pk}/delete/")
        assert response.status_code == 302

    def test_selective_transfer_task_reset_view(self):
        """
        Test that a user can successfully reset a task when business rules allow it.

        Tasks can be reset if they have CANCELED, SUCCESS, WARNING, or FAILURE status.
        After reset, the task status becomes PENDING.

        Arrange: Create an active user, a job, and a task with FAILURE status.
        Act: Log in the user and make a POST request to the task's reset URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = SelectiveTransferJobFactory.create(owner=user)

        task = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/selective-transfer/tasks/{task.pk}/reset/")
        assert response.status_code == 302

    def test_selective_transfer_task_kill_view(self):
        """
        Test that a staff user can successfully kill a running task.

        Arrange: Create an active staff user, a job, and an in-progress task.
        Act: Log in the user and make a POST request to the task's kill URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = SelectiveTransferJobFactory.create(owner=user)
        task = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.IN_PROGRESS)
        client.force_login(user)

        response = client.post(f"/selective-transfer/tasks/{task.pk}/kill/")
        assert response.status_code == 302
