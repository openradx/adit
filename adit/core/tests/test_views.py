import pytest
from adit_radis_shared.accounts.factories import UserFactory
from django.test import Client
from django.urls import reverse
from procrastinate.contrib.django.models import ProcrastinateJob

from adit.core.models import DicomJob, DicomTask

from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory
from .example_app.models import ExampleTransferJob, ExampleTransferTask


class TestExampleTransferJobDeleteView:
    @pytest.mark.django_db
    def test_job_can_be_deleted(self, client: Client):
        user = UserFactory.create()
        client.force_login(user)

        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING, owner=user)
        task = ExampleTransferTaskFactory.create(
            status=DicomTask.Status.PENDING,
            job=job,
        )
        task.queue_pending_task()

        assert ProcrastinateJob.objects.count() == 1

        response = client.post(reverse("example_transfer_job_delete", args=[job.pk]))

        assert response.status_code == 302
        assert ExampleTransferJob.objects.count() == 0
        assert ExampleTransferTask.objects.count() == 0
        assert ProcrastinateJob.objects.count() == 0

    @pytest.mark.django_db
    def test_non_deletable_job_cannot_be_deleted(self, client: Client):
        user = UserFactory.create()
        client.force_login(user)

        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING, owner=user)
        task = ExampleTransferTaskFactory.create(
            status=DicomTask.Status.PENDING,
            job=job,
        )

        task.queue_pending_task()

        job.status = DicomJob.Status.IN_PROGRESS
        job.save()

        task.status = DicomTask.Status.IN_PROGRESS
        task.save()

        assert ProcrastinateJob.objects.count() == 1

        response = client.post(reverse("example_transfer_job_delete", args=[job.pk]))

        assert response.status_code == 400
        assert ExampleTransferJob.objects.count() == 1
        assert ExampleTransferTask.objects.count() == 1
        assert ProcrastinateJob.objects.count() == 1


class TestExampleTransferJobCancelView:
    @pytest.mark.django_db
    def test_job_can_be_canceled(self, client: Client):
        user = UserFactory.create()
        client.force_login(user)

        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING, owner=user)
        task = ExampleTransferTaskFactory.create(
            status=DicomTask.Status.PENDING,
            job=job,
        )
        task.queue_pending_task()

        response = client.post(reverse("example_transfer_job_cancel", args=[job.pk]))

        assert response.status_code == 302

        job.refresh_from_db()
        assert job.status == DicomJob.Status.CANCELED

        task.refresh_from_db()
        assert task.status == DicomTask.Status.CANCELED

        assert ProcrastinateJob.objects.count() == 0

    @pytest.mark.django_db
    def test_non_cancelable_job_cannot_be_canceled(self, client: Client):
        user = UserFactory.create()
        client.force_login(user)

        job = ExampleTransferJobFactory.create(status=DicomJob.Status.SUCCESS, owner=user)
        task = ExampleTransferTaskFactory.create(
            status=DicomTask.Status.SUCCESS,
            job=job,
        )

        response = client.post(reverse("example_transfer_job_cancel", args=[job.pk]))

        assert response.status_code == 400

        job.refresh_from_db()
        assert job.status == DicomJob.Status.SUCCESS

        task.refresh_from_db()
        assert task.status == DicomTask.Status.SUCCESS


class TestHealthView:
    @pytest.mark.django_db
    def test_health_endpoint_returns_ok(self, client: Client):
        response = client.get(reverse("health"))

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
