"""Behavioural HTTP tests for the mass_transfer views.

These go beyond "page loads / status == 200" and assert real outcomes:
permission gating (403), owner-scoped querysets (404 for foreign jobs),
staff-vs-owner CSV-export scoping, and DB side effects of a create POST.
"""

import json

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission, add_user_to_group
from django.test import Client
from django.urls import reverse

from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.models import DicomJob
from adit.core.utils.auth_utils import grant_access

from ..factories import MassTransferJobFactory, MassTransferTaskFactory
from ..models import MassTransferJob, MassTransferTask, MassTransferVolume


@pytest.fixture
def settings_no_toolbar(settings):
    """Disable the debug toolbar so HTML views don't blow up with the known
    `NoReverseMatch: 'djdt'` quirk under the development settings module."""
    settings.DEBUG = False
    settings.DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}
    return settings


def _make_volume(job: MassTransferJob, **overrides) -> MassTransferVolume:
    defaults = dict(
        job=job,
        partition_key="2024-01-01",
        study_instance_uid="1.2.3",
        series_instance_uid="1.2.3.4",
        study_datetime="2024-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return MassTransferVolume.objects.create(**defaults)


# --- Permission gating on the create view -----------------------------------


@pytest.mark.django_db
def test_create_view_forbidden_without_permission(client: Client, settings_no_toolbar):
    """A logged-in user lacking `add_masstransferjob` is denied (403)."""
    user = UserFactory.create(is_active=True)
    client.force_login(user)

    response = client.get(reverse("mass_transfer_job_create"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_view_allowed_with_permission(client: Client, settings_no_toolbar):
    """With the permission granted the create form renders."""
    user = UserFactory.create(is_active=True)
    group = GroupFactory.create()
    add_user_to_group(user, group)
    add_permission(user, "mass_transfer", "add_masstransferjob")
    client.force_login(user)

    response = client.get(reverse("mass_transfer_job_create"))

    assert response.status_code == 200


# --- Owner-scoped detail view -----------------------------------------------


@pytest.mark.django_db
def test_detail_view_owner_can_see_own_job(client: Client, settings_no_toolbar):
    owner = UserFactory.create(is_active=True)
    job = MassTransferJobFactory.create(owner=owner)
    client.force_login(owner)

    response = client.get(reverse("mass_transfer_job_detail", args=[job.pk]))

    assert response.status_code == 200
    assert response.context["job"].pk == job.pk


@pytest.mark.django_db
def test_detail_view_foreign_job_is_not_found(client: Client, settings_no_toolbar):
    """A non-staff user must NOT see another user's job: owner-scoped queryset
    turns the foreign pk into a 404 (not a 200, not a 403)."""
    owner = UserFactory.create(is_active=True)
    other = UserFactory.create(is_active=True)
    job = MassTransferJobFactory.create(owner=owner)
    client.force_login(other)

    response = client.get(reverse("mass_transfer_job_detail", args=[job.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_view_staff_can_see_foreign_job(client: Client, settings_no_toolbar):
    """Staff bypass owner scoping and may view any job."""
    owner = UserFactory.create(is_active=True)
    staff = UserFactory.create(is_active=True, is_staff=True)
    job = MassTransferJobFactory.create(owner=owner)
    client.force_login(staff)

    response = client.get(reverse("mass_transfer_job_detail", args=[job.pk]))

    assert response.status_code == 200
    assert response.context["job"].pk == job.pk


# --- CSV export staff-vs-owner scoping --------------------------------------


@pytest.mark.django_db
def test_csv_export_owner_gets_own_volumes(client: Client):
    owner = UserFactory.create(is_active=True)
    job = MassTransferJobFactory.create(owner=owner, pseudonym_salt="abc123")
    _make_volume(job, patient_id="PID-1", series_instance_uid="9.9.9.1")
    _make_volume(job, patient_id="PID-2", series_instance_uid="9.9.9.2")
    client.force_login(owner)

    response = client.get(reverse("mass_transfer_job_csv_export", args=[job.pk]))

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert f'filename="mass_transfer_job_{job.pk}.csv"' in response["Content-Disposition"]

    body = response.getvalue().decode()
    # Salt is emitted as a leading comment line, then the header, then rows.
    assert "# Pseudonym salt: abc123" in body
    assert "patient_id" in body  # header row
    assert "PID-1" in body
    assert "PID-2" in body


@pytest.mark.django_db
def test_csv_export_foreign_job_is_not_found_for_owner(client: Client):
    """A non-staff user cannot export another user's job (owner-scoped → 404)."""
    owner = UserFactory.create(is_active=True)
    other = UserFactory.create(is_active=True)
    job = MassTransferJobFactory.create(owner=owner)
    _make_volume(job, patient_id="SECRET")
    client.force_login(other)

    response = client.get(reverse("mass_transfer_job_csv_export", args=[job.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_csv_export_staff_can_export_foreign_job(client: Client):
    """Staff scoping covers all jobs: a staff user can export a job they don't own."""
    owner = UserFactory.create(is_active=True)
    staff = UserFactory.create(is_active=True, is_staff=True)
    job = MassTransferJobFactory.create(owner=owner)
    _make_volume(job, patient_id="PID-STAFF", series_instance_uid="7.7.7.1")
    client.force_login(staff)

    response = client.get(reverse("mass_transfer_job_csv_export", args=[job.pk]))

    assert response.status_code == 200
    assert "PID-STAFF" in response.getvalue().decode()


@pytest.mark.django_db
def test_csv_export_no_salt_omits_salt_comment(client: Client):
    owner = UserFactory.create(is_active=True)
    job = MassTransferJobFactory.create(owner=owner, pseudonymize=False, pseudonym_salt="")
    _make_volume(job)
    client.force_login(owner)

    response = client.get(reverse("mass_transfer_job_csv_export", args=[job.pk]))

    assert response.status_code == 200
    assert "# Pseudonym salt:" not in response.getvalue().decode()


# --- Create POST writes the expected DB objects -----------------------------


@pytest.mark.django_db(transaction=True)
def test_create_post_creates_job_and_tasks(client: Client, settings_no_toolbar):
    """A valid POST to the create view must persist a MassTransferJob owned by
    the requester plus the partitioned MassTransferTasks, and (since
    START_MASS_TRANSFER_UNVERIFIED is True) move the job to PENDING.

    transaction=True is required so the Procrastinate queueing job that
    form_valid defers is actually committed/visible.
    """
    user = UserFactory.create(is_active=True)
    group = GroupFactory.create()
    add_user_to_group(user, group)
    add_permission(user, "mass_transfer", "add_masstransferjob")

    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    client.force_login(user)

    assert MassTransferJob.objects.count() == 0

    response = client.post(
        reverse("mass_transfer_job_create"),
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
    )

    # CreateView redirects to the new job's absolute url on success.
    assert response.status_code == 302, getattr(response, "context", None)

    job = MassTransferJob.objects.get()
    assert job.owner == user
    # Daily partitions across a 3-day inclusive window -> 3 tasks.
    tasks = MassTransferTask.objects.filter(job=job)
    assert tasks.count() == 3
    assert {t.source_id for t in tasks} == {source.pk}
    assert {t.destination_id for t in tasks} == {destination.pk}
    # START_MASS_TRANSFER_UNVERIFIED is True -> job is verified/queued.
    assert job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_create_post_without_permission_creates_nothing(client: Client, settings_no_toolbar):
    """Posting without the add permission is forbidden and writes no rows."""
    user = UserFactory.create(is_active=True)
    source = DicomServerFactory.create()
    destination = DicomFolderFactory.create()
    client.force_login(user)

    response = client.post(
        reverse("mass_transfer_job_create"),
        data={
            "source": source.pk,
            "destination": destination.pk,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "partition_granularity": "daily",
            "pseudonymize": False,
            "pseudonym_salt": "",
            "filters_json": json.dumps([{"modality": "CT"}]),
        },
    )

    assert response.status_code == 403
    assert MassTransferJob.objects.count() == 0


# --- Detail/CSV require authentication --------------------------------------


@pytest.mark.django_db
def test_detail_view_anonymous_redirected_to_login(client: Client, settings_no_toolbar):
    job = MassTransferJobFactory.create()

    response = client.get(reverse("mass_transfer_job_detail", args=[job.pk]))

    # LoginRequiredMixin redirects unauthenticated users to the login page.
    assert response.status_code == 302
    assert "/accounts/login" in response["Location"]


# --- Task detail owner scoping ----------------------------------------------


@pytest.mark.django_db
def test_task_detail_foreign_task_is_not_found(client: Client, settings_no_toolbar):
    owner = UserFactory.create(is_active=True)
    other = UserFactory.create(is_active=True)
    job = MassTransferJobFactory.create(owner=owner)
    task = MassTransferTaskFactory.create(job=job)
    client.force_login(other)

    response = client.get(reverse("mass_transfer_task_detail", args=[task.pk]))

    assert response.status_code == 404
