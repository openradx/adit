import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

from adit.core.models import DicomJob, DicomTask

from ..factories import SelectiveTransferJobFactory, SelectiveTransferTaskFactory
from ..models import SelectiveTransferJob


@pytest.fixture
def settings_no_toolbar(settings):
    """Disable the debug toolbar to avoid the known `NoReverseMatch: 'djdt'`
    quirk when rendering HTML views under the development settings module."""
    settings.DEBUG = False
    settings.DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}
    return settings


@pytest.mark.django_db
def test_selective_transfer_job_list_view(client: Client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)

    response = client.get("/selective-transfer/jobs/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_selective_transfer_job_create_view(client: Client):
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


@pytest.mark.django_db
def test_selective_transfer_job_detail_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user)
    client.force_login(user)

    response = client.get(f"/selective-transfer/jobs/{job.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_selective_transfer_job_verify_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.UNVERIFIED)
    client.force_login(user)

    response = client.post(f"/selective-transfer/jobs/{job.pk}/verify/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_job_cancel_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
    client.force_login(user)

    response = client.post(f"/selective-transfer/jobs/{job.pk}/cancel/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_job_resume_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.CANCELED)
    client.force_login(user)

    response = client.post(f"/selective-transfer/jobs/{job.pk}/resume/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_job_retry_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.FAILURE)
    client.force_login(user)

    response = client.post(f"/selective-transfer/jobs/{job.pk}/retry/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_job_restart_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    job = SelectiveTransferJobFactory.create(status=DicomJob.Status.FAILURE)
    client.force_login(user)

    response = client.post(f"/selective-transfer/jobs/{job.pk}/restart/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_task_detail_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user)
    task = SelectiveTransferTaskFactory.create(job=job)
    client.force_login(user)

    response = client.get(f"/selective-transfer/tasks/{task.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_selective_transfer_job_delete_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user, status=DicomJob.Status.PENDING)
    client.force_login(user)

    response = client.post(f"/selective-transfer/jobs/{job.pk}/delete/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_task_delete_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user)
    job.tasks.all().delete()
    task_to_delete = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.PENDING)

    client.force_login(user)

    response = client.post(f"/selective-transfer/tasks/{task_to_delete.pk}/delete/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_task_reset_view(client: Client):
    user = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=user)

    task = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
    client.force_login(user)

    response = client.post(f"/selective-transfer/tasks/{task.pk}/reset/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_selective_transfer_task_kill_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    job = SelectiveTransferJobFactory.create(owner=user)
    task = SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.IN_PROGRESS)
    client.force_login(user)

    response = client.post(f"/selective-transfer/tasks/{task.pk}/kill/")
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Behavioural tests: assert real outcomes (permission gating, owner scoping,
# and DB state changes), not just status codes.
# ---------------------------------------------------------------------------


def _add_create_permission(user):
    permission = Permission.objects.get(
        codename="add_selectivetransferjob",
        content_type=ContentType.objects.get(
            app_label="selective_transfer", model="selectivetransferjob"
        ),
    )
    user.user_permissions.add(permission)


@pytest.mark.django_db
def test_create_view_forbidden_without_permission(client: Client, settings_no_toolbar):
    """A logged-in user without `add_selectivetransferjob` is denied (403)."""
    user = UserFactory.create(is_active=True)
    client.force_login(user)

    response = client.get(reverse("selective_transfer_job_create"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_view_allowed_with_permission(client: Client, settings_no_toolbar):
    user = UserFactory.create(is_active=True)
    _add_create_permission(user)
    client.force_login(user)

    response = client.get(reverse("selective_transfer_job_create"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_create_view_post_is_websocket_only(client: Client, settings_no_toolbar):
    """The HTTP create POST is intentionally disabled (form processing happens
    over WebSockets in the consumer), so a POST must raise BadRequest and must
    NOT create a job. DB-state-after-create is therefore covered behaviourally
    via the consumer's transfer path (see tests/test_consumer.py), not here.
    """
    user = UserFactory.create(is_active=True)
    _add_create_permission(user)
    client.force_login(user)

    assert SelectiveTransferJob.objects.count() == 0

    # The view raises BadRequest; Django's exception handler turns that into a
    # 400 response (the test client does not re-raise BadRequest). Either way,
    # no job is created.
    response = client.post(reverse("selective_transfer_job_create"), data={})

    assert response.status_code == 400
    assert SelectiveTransferJob.objects.count() == 0


# --- Owner-scoped detail view -----------------------------------------------


@pytest.mark.django_db
def test_detail_view_owner_sees_own_job(client: Client, settings_no_toolbar):
    owner = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=owner)
    client.force_login(owner)

    response = client.get(reverse("selective_transfer_job_detail", args=[job.pk]))

    assert response.status_code == 200
    assert response.context["job"].pk == job.pk


@pytest.mark.django_db
def test_detail_view_foreign_job_is_not_found(client: Client, settings_no_toolbar):
    """A non-staff user must not access another user's job: owner-scoped
    queryset turns the foreign pk into a 404."""
    owner = UserFactory.create(is_active=True)
    other = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=owner)
    client.force_login(other)

    response = client.get(reverse("selective_transfer_job_detail", args=[job.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_view_staff_sees_foreign_job(client: Client, settings_no_toolbar):
    owner = UserFactory.create(is_active=True)
    staff = UserFactory.create(is_active=True, is_staff=True)
    job = SelectiveTransferJobFactory.create(owner=owner)
    client.force_login(staff)

    response = client.get(reverse("selective_transfer_job_detail", args=[job.pk]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_task_detail_foreign_task_is_not_found(client: Client, settings_no_toolbar):
    owner = UserFactory.create(is_active=True)
    other = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=owner)
    task = SelectiveTransferTaskFactory.create(job=job)
    client.force_login(other)

    response = client.get(reverse("selective_transfer_task_detail", args=[task.pk]))

    assert response.status_code == 404


# --- Mutating POSTs change DB state -----------------------------------------


@pytest.mark.django_db
def test_verify_post_moves_job_to_pending(client: Client):
    """A staff verify POST must flip the job's status from UNVERIFIED to
    PENDING in the database (not merely redirect)."""
    staff = UserFactory.create(is_active=True, is_staff=True)
    job = SelectiveTransferJobFactory.create(owner=staff, status=DicomJob.Status.UNVERIFIED)
    # Give the job a pending task so queue_pending_tasks has something to defer.
    SelectiveTransferTaskFactory.create(job=job, status=DicomTask.Status.PENDING)
    client.force_login(staff)

    response = client.post(reverse("selective_transfer_job_verify", args=[job.pk]))

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_verify_post_forbidden_for_non_staff(client: Client):
    """Verify is staff-only (UserPassesTestMixin): a plain owner is forbidden
    and the job stays UNVERIFIED."""
    owner = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=owner, status=DicomJob.Status.UNVERIFIED)
    client.force_login(owner)

    response = client.post(reverse("selective_transfer_job_verify", args=[job.pk]))

    assert response.status_code == 403
    job.refresh_from_db()
    assert job.status == DicomJob.Status.UNVERIFIED


@pytest.mark.django_db
def test_delete_post_removes_job_from_db(client: Client):
    """A delete POST on a deletable (PENDING) job must remove it from the DB."""
    owner = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=owner, status=DicomJob.Status.PENDING)
    client.force_login(owner)

    response = client.post(reverse("selective_transfer_job_delete", args=[job.pk]))

    assert response.status_code == 302
    assert not SelectiveTransferJob.objects.filter(pk=job.pk).exists()


@pytest.mark.django_db
def test_delete_post_foreign_job_is_not_found_and_preserved(client: Client):
    """A non-owner cannot delete another user's job: owner-scoped queryset →
    404, and the job remains in the DB."""
    owner = UserFactory.create(is_active=True)
    other = UserFactory.create(is_active=True)
    job = SelectiveTransferJobFactory.create(owner=owner, status=DicomJob.Status.PENDING)
    client.force_login(other)

    response = client.post(reverse("selective_transfer_job_delete", args=[job.pk]))

    assert response.status_code == 404
    assert SelectiveTransferJob.objects.filter(pk=job.pk).exists()
