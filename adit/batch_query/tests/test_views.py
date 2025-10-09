import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from adit.core.models import DicomJob, DicomTask

from ..factories import BatchQueryJobFactory, BatchQueryTaskFactory


@pytest.mark.django_db
def test_batch_query_job_list_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)

    response = client.get("/batch-query/jobs/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_job_create_view(client: Client):
    user = UserFactory.create(is_active=True)
    permission = Permission.objects.get(
        codename="add_batchqueryjob",
        content_type=ContentType.objects.get(app_label="batch_query", model="batchqueryjob"),
    )
    user.user_permissions.add(permission)
    client.force_login(user)

    response = client.get("/batch-query/jobs/new/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_job_detail_view(client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user)
    client.force_login(user)

    response = client.get(f"/batch-query/jobs/{job.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_job_verify_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.UNVERIFIED)
    client.force_login(user)

    response = client.post(f"/batch-query/jobs/{job.pk}/verify/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_job_cancel_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
    client.force_login(user)

    response = client.post(f"/batch-query/jobs/{job.pk}/cancel/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_job_resume_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.CANCELED)
    client.force_login(user)

    response = client.post(f"/batch-query/jobs/{job.pk}/resume/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_job_retry_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
    client.force_login(user)

    response = client.post(f"/batch-query/jobs/{job.pk}/retry/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_job_restart_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
    client.force_login(user)

    response = client.post(f"/batch-query/jobs/{job.pk}/restart/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_job_delete_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
    client.force_login(user)

    response = client.post(f"/batch-query/jobs/{job.pk}/delete/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_result_list_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user)
    client.force_login(user)

    response = client.get(f"/batch-query/jobs/{job.pk}/results/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_result_download_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user)
    client.force_login(user)

    response = client.get(f"/batch-query/jobs/{job.pk}/download/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_task_detail_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user)
    task = BatchQueryTaskFactory.create(job=job)
    client.force_login(user)

    response = client.get(f"/batch-query/tasks/{task.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_task_delete_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user)
    task_to_delete = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.PENDING)

    client.force_login(user)

    response = client.post(f"/batch-query/tasks/{task_to_delete.pk}/delete/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_task_kill_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    job = BatchQueryJobFactory.create(owner=user)
    task = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.IN_PROGRESS)
    client.force_login(user)

    response = client.post(f"/batch-query/tasks/{task.pk}/kill/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_task_reset_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = BatchQueryJobFactory.create(owner=user)
    task = BatchQueryTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
    client.force_login(user)

    response = client.post(f"/batch-query/tasks/{task.pk}/reset/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_query_help_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)

    response = client.get("/batch-query/help/", HTTP_HX_REQUEST="true")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_query_update_preferences_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)

    response = client.post(
        "/batch-query/update-preferences/",
        data={"batch_query_urgent": "true"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
