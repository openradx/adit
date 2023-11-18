import pytest
from django.test import Client
from django.urls import reverse

from adit.accounts.factories import UserFactory

from ..models import DicomJob, DicomTask, QueuedTask
from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory


@pytest.mark.django_db(transaction=True)
def test_job_can_be_canceled(client: Client):
    user = UserFactory.create()
    client.force_login(user)

    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING, owner=user)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING,
        job=dicom_job,
    )
    QueuedTask.objects.create(content_object=dicom_task, priority=5)

    client.post(reverse("example_transfer_job_cancel", args=[dicom_job.pk]))

    dicom_job.refresh_from_db()
    assert dicom_job.status == DicomJob.Status.CANCELED

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.CANCELED

    assert QueuedTask.objects.count() == 0
