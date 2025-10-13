import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from procrastinate.contrib.django.models import ProcrastinateJob
from pytest_django.asserts import assertTemplateUsed
from pytest_django.fixtures import SettingsWrapper

from adit.batch_transfer.factories import BatchTransferJobFactory, BatchTransferTaskFactory
from adit.batch_transfer.models import BatchTransferJob, BatchTransferTask
from adit.batch_transfer.utils.testing_helpers import create_batch_transfer_group, create_form_data
from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access


@pytest.mark.django_db
def test_user_must_be_logged_in_to_access_view(client: Client):
    response = client.get(reverse("batch_transfer_job_create"))
    assert response.status_code == 302
    response = client.post(reverse("batch_transfer_job_create"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_user_must_have_permission_to_access_view(client: Client):
    user = UserFactory.create()
    client.force_login(user)
    response = client.get(reverse("batch_transfer_job_create"))
    assert response.status_code == 403
    response = client.post(reverse("batch_transfer_job_create"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_logged_in_user_with_permission_can_access_form(client: Client):
    user = UserFactory.create()
    group = create_batch_transfer_group()
    add_user_to_group(user, group)
    client.force_login(user)
    response = client.get(reverse("batch_transfer_job_create"))
    assert response.status_code == 200
    assertTemplateUsed(response, "batch_transfer/batch_transfer_job_form.html")


@pytest.mark.django_db
def test_batch_job_created_and_enqueued_with_auto_verify(client: Client, settings: SettingsWrapper):
    settings.START_BATCH_TRANSFER_UNVERIFIED = True

    user = UserFactory.create()
    group = create_batch_transfer_group()
    add_user_to_group(user, group)

    form_data = create_form_data()
    source_server = DicomServer.objects.get(pk=form_data["source"])
    destination_server = DicomServer.objects.get(pk=form_data["destination"])
    grant_access(group, source_server, source=True)
    grant_access(group, destination_server, destination=True)

    client.force_login(user)
    client.post(reverse("batch_transfer_job_create"), form_data)

    job = BatchTransferJob.objects.first()
    assert job and job.tasks.count() == 3
    assert ProcrastinateJob.objects.count() == 3


@pytest.mark.django_db
def test_batch_job_created_and_not_enqueued_without_auto_verify(
    client: Client, settings: SettingsWrapper
):
    settings.START_BATCH_TRANSFER_UNVERIFIED = False

    user = UserFactory.create()
    group = create_batch_transfer_group()
    add_user_to_group(user, group)

    form_data = create_form_data()
    source_server = DicomServer.objects.get(pk=form_data["source"])
    destination_server = DicomServer.objects.get(pk=form_data["destination"])
    grant_access(group, source_server, source=True)
    grant_access(group, destination_server, destination=True)

    client.force_login(user)
    client.post(reverse("batch_transfer_job_create"), form_data)

    job = BatchTransferJob.objects.first()
    assert job and job.tasks.count() == 3
    assert ProcrastinateJob.objects.count() == 0


@pytest.mark.django_db
def test_job_cant_be_created_with_missing_fields(client: Client):
    user = UserFactory.create()
    group = create_batch_transfer_group()
    add_user_to_group(user, group)
    client.force_login(user)
    form_data = create_form_data()
    for key_to_exclude in form_data:
        invalid_form_data = form_data.copy()
        del invalid_form_data[key_to_exclude]
        response = client.post(reverse("batch_transfer_job_create"), invalid_form_data)
        assert len(response.context["form"].errors) > 0
        assert BatchTransferJob.objects.first() is None


@pytest.mark.django_db
def test_batch_transfer_job_list_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    response = client.get("/batch-transfer/jobs/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_transfer_job_create_view(client: Client):
    user = UserFactory.create(is_active=True)
    permission = Permission.objects.get(
        codename="add_batchtransferjob",
        content_type=ContentType.objects.get_for_model(BatchTransferJob),
    )
    client.force_login(user)
    user.user_permissions.add(permission)
    response = client.post("/batch-transfer/jobs/new/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_transfer_job_detail_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user)
    response = client.get(f"/batch-transfer/jobs/{job.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_transfer_job_delete_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.PENDING)
    response = client.post(f"/batch-transfer/jobs/{job.pk}/delete/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_job_verify_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.UNVERIFIED)
    response = client.post(f"/batch-transfer/jobs/{job.pk}/verify/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_job_cancel_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.PENDING)
    response = client.post(f"/batch-transfer/jobs/{job.pk}/cancel/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_job_restart_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.FAILURE)
    response = client.post(f"/batch-transfer/jobs/{job.pk}/restart/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_update_preferences_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    response = client.post("/batch-transfer/update-preferences/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_transfer_help_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    response = client.get("/batch-transfer/help/", HTTP_HX_REQUEST="true")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_transfer_job_resume_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.CANCELED)
    response = client.post(f"/batch-transfer/jobs/{job.pk}/resume/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_job_retry_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user, status=BatchTransferJob.Status.FAILURE)
    response = client.post(f"/batch-transfer/jobs/{job.pk}/retry/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_task_detail_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user)
    task = BatchTransferTaskFactory.create(job=job)
    response = client.get(f"/batch-transfer/tasks/{task.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_batch_transfer_task_delete_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user)
    task_to_delete = BatchTransferTaskFactory.create(
        job=job, status=BatchTransferTask.Status.PENDING
    )

    response = client.post(f"/batch-transfer/tasks/{task_to_delete.pk}/delete/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_task_reset_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user)
    task = BatchTransferTaskFactory.create(job=job, status=BatchTransferTask.Status.FAILURE)
    response = client.post(f"/batch-transfer/tasks/{task.pk}/reset/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_batch_transfer_task_kill_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = BatchTransferJobFactory.create(owner=user)
    task = BatchTransferTaskFactory.create(job=job, status=BatchTransferTask.Status.IN_PROGRESS)
    response = client.post(f"/batch-transfer/tasks/{task.pk}/kill/")
    assert response.status_code == 302
