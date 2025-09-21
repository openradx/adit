import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from adit.core.models import DicomJob, DicomTask

from ..factories import BatchQueryJobFactory, BatchQueryTaskFactory


@pytest.mark.django_db
class TestBatchQuery:
    def test_batch_query_job_list_view(self):
        """
        Test that a logged-in user can successfully access the job list view.

        Arrange: Create an active user.
        Act: Log in the user and make a GET request to the job list URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)

        response = client.get("/batch-query/jobs/")
        assert response.status_code == 200

    def test_batch_query_job_create_view(self):
        """
        Test that a user with the correct permission can access the job creation page.

        Arrange: Create an active user and give them the 'add_batchqueryjob' permission.
        Act: Log in the user and make a GET request to the new job URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="add_batchqueryjob",
            content_type=ContentType.objects.get(app_label="batch_query", model="batchqueryjob"),
        )
        user.user_permissions.add(permission)
        client.force_login(user)

        response = client.get("/batch-query/jobs/new/")
        assert response.status_code == 200

    def test_batch_query_job_detail_view(self):
        """
        Test that a logged-in user can view the detail page of a specific job.

        Arrange: Create an active user and a job owned by that user.
        Act: Log in the user and make a GET request to the job's detail URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        client.force_login(user)

        response = client.get(f"/batch-query/jobs/{job.pk}/")
        assert response.status_code == 200

    def test_batch_query_job_verify_view(self):
        """
        Test that a staff user can successfully verify an unverified job.

        Arrange: Create an active staff user and an unverified job.
        Act: Log in the user and make a POST request to the job's verify URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.UNVERIFIED)
        client.force_login(user)

        response = client.post(f"/batch-query/jobs/{job.pk}/verify/")
        assert response.status_code == 302

    def test_batch_query_job_cancel_view(self):
        """
        Test that a user can successfully cancel a pending job.

        Arrange: Create an active user and a pending job.
        Act: Log in the user and make a POST request to the job's cancel URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
        client.force_login(user)

        response = client.post(f"/batch-query/jobs/{job.pk}/cancel/")
        assert response.status_code == 302

    def test_batch_query_job_resume_view(self):
        """
        Test that a user can successfully resume a canceled job.

        Arrange: Create an active user and a canceled job.
        Act: Log in the user and make a POST request to the job's resume URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.CANCELED)
        client.force_login(user)

        response = client.post(f"/batch-query/jobs/{job.pk}/resume/")
        assert response.status_code == 302

    def test_batch_query_job_retry_view(self):
        """
        Test that a user can successfully retry a failed job.

        Arrange: Create an active user and a failed job.
        Act: Log in the user and make a POST request to the job's retry URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/batch-query/jobs/{job.pk}/retry/")
        assert response.status_code == 302

    def test_batch_query_job_restart_view(self):
        """
        Test that a staff user can successfully restart a failed job.

        Arrange: Create an active staff user and a failed job.
        Act: Log in the user and make a POST request to the job's restart URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/batch-query/jobs/{job.pk}/restart/")
        assert response.status_code == 302

    def test_batch_query_job_delete_view(self):
        """
        Test that job deletion is properly restricted.

        Jobs can only be deleted if they have UNVERIFIED or PENDING status
        and no non-pending tasks. Most other statuses are not deletable.

        Arrange: Create an active user and a job owned by that user.
        Act: Log in the user and attempt to delete the job.
        Assert: The operation is rejected with status 400 (Bad Request).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        client.force_login(user)

        response = client.post(f"/batch-query/jobs/{job.pk}/delete/")
        assert response.status_code == 400

    def test_batch_query_result_list_view(self):
        """
        Test that a logged-in user can view the results list of a specific job.

        Arrange: Create an active user and a job owned by that user.
        Act: Log in the user and make a GET request to the job's results URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        client.force_login(user)

        response = client.get(f"/batch-query/jobs/{job.pk}/results/")
        assert response.status_code == 200

    def test_batch_query_result_download_view(self):
        """
        Test that a logged-in user can download results of a specific job.

        Arrange: Create an active user and a job owned by that user.
        Act: Log in the user and make a GET request to the job's download URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        client.force_login(user)

        response = client.get(f"/batch-query/jobs/{job.pk}/download/")
        assert response.status_code == 200

    def test_batch_query_task_detail_view(self):
        """
        Test that a logged-in user can view the detail page of a specific task.

        Arrange: Create an active user, a job, and a task belonging to that job.
        Act: Log in the user and make a GET request to the task's detail URL.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        task = BatchQueryTaskFactory.create(job=job)
        client.force_login(user)

        response = client.get(f"/batch-query/tasks/{task.pk}/")
        assert response.status_code == 200

    def test_batch_query_task_delete_view(self):
        """
        Test that task deletion is properly restricted.

        Arrange: Create an active user, a job, and a task.
        Act: Log in the user and attempt to delete the task.
        Assert: The operation would be processed according to business rules.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        task_to_delete = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.PENDING)
        remaining_task = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

        client.force_login(user)

        response = client.post(f"/batch-query/tasks/{task_to_delete.pk}/delete/")
        assert response.status_code == 302

    def test_batch_query_task_kill_view(self):
        """
        Test that a staff user can successfully kill a running task.

        Arrange: Create an active staff user, a job, and an in-progress task.
        Act: Log in the user and make a POST request to the task's kill URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True, is_staff=True)
        job = BatchQueryJobFactory.create(owner=user)
        task = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.IN_PROGRESS)
        client.force_login(user)

        response = client.post(f"/batch-query/tasks/{task.pk}/kill/")
        assert response.status_code == 302

    def test_batch_query_task_reset_view(self):
        """
        Test that a user can successfully reset a failed task.

        Arrange: Create an active user, a job, and a failed task.
        Act: Log in the user and make a POST request to the task's reset URL.
        Assert: The response status code is 302 (Redirect), indicating success.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        job = BatchQueryJobFactory.create(owner=user)
        task = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
        client.force_login(user)

        response = client.post(f"/batch-query/tasks/{task.pk}/reset/")
        assert response.status_code == 302

    def test_batch_query_help_view(self):
        """
        Test that the help page is accessible to logged-in users.

        The help view is an HtmxTemplateView which requires an HTMX request.

        Arrange: Create an active user.
        Act: Log in the user and make a GET request to the help URL with HTMX headers.
        Assert: The response status code is 200 (OK).
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)

        response = client.get("/batch-query/help/", HTTP_HX_REQUEST="true")
        assert response.status_code == 200

    def test_batch_query_update_preferences_view(self):
        """
        Test that a logged-in user can access the update preferences endpoint.

        The view only accepts specific preference keys defined in allowed_keys.
        Valid keys are: batch_query_source, batch_query_urgent, batch_query_send_finished_mail

        Arrange: Create an active user.
        Act: Log in the user and make a POST request with valid preference data.
        Assert: The response status code indicates successful processing.
        """
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)

        response = client.post(
            "/batch-query/update-preferences/",
            data={"batch_query_urgent": "true"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
