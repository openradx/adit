import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.test import Client

from adit.mass_transfer.factories import MassTransferJobFactory, MassTransferTaskFactory
from adit.mass_transfer.models import MassTransferTask


@pytest.mark.django_db
def test_mass_transfer_task_force_retry_view(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = MassTransferJobFactory.create(owner=user)
    task = MassTransferTaskFactory.create(
        job=job, status=MassTransferTask.Status.SUCCESS
    )
    response = client.post(f"/mass-transfer/tasks/{task.pk}/force-retry/")
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == MassTransferTask.Status.PENDING


@pytest.mark.django_db
def test_mass_transfer_task_force_retry_in_progress(client: Client):
    user = UserFactory.create(is_active=True, is_staff=True)
    client.force_login(user)
    job = MassTransferJobFactory.create(owner=user)
    task = MassTransferTaskFactory.create(
        job=job, status=MassTransferTask.Status.IN_PROGRESS
    )
    response = client.post(f"/mass-transfer/tasks/{task.pk}/force-retry/")
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == MassTransferTask.Status.PENDING


@pytest.mark.django_db
def test_mass_transfer_task_force_retry_forbidden_for_non_staff(client: Client):
    user = UserFactory.create(is_active=True, is_staff=False)
    client.force_login(user)
    job = MassTransferJobFactory.create(owner=user)
    task = MassTransferTaskFactory.create(
        job=job, status=MassTransferTask.Status.SUCCESS
    )
    response = client.post(f"/mass-transfer/tasks/{task.pk}/force-retry/")
    assert response.status_code == 403
