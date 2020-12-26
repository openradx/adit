from unittest.mock import patch
import pytest
from pytest_django.asserts import (  # pylint: disable=no-name-in-module
    assertTemplateUsed,
)
from django.contrib.auth.models import Group
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from adit.accounts.factories import UserFactory
from adit.core.factories import DicomServerFactory
from ..models import BatchTransferJob

csv_data = b"""\
Batch ID;Patient ID;Patient Name;Birth Date;Study Date;Modality;Pseudonym;
1;10007;Papaya, Pamela;29.08.1976;19.08.2018;MR;ABU5QZL9;
2;10002;Banana, Ben;18.02.1962;27.03.2018;CT;DEDH6SVQ;
3;10002;Banana, Ben;18.02.1962;15.09.2019;MR;DEDH6SVQ;
"""

# Somehow the form data must be always generated from scratch (maybe cause of the
# SimpleUploadedFile) otherwise tests fail.
@pytest.fixture
def form_data(db):
    return {
        "source": DicomServerFactory().id,
        "destination": DicomServerFactory().id,
        "project_name": "Apollo project",
        "project_description": "Fly to the moon",
        "ethics_committee_approval": "on",
        "csv_file": SimpleUploadedFile(
            name="sample_sheet.csv", content=csv_data, content_type="text/csv"
        ),
    }


@pytest.fixture
def user_without_permission(db):
    return UserFactory()


@pytest.fixture
def user_with_permission(db):
    user = UserFactory()
    batch_transferrers_group = Group.objects.get(name="batch_transferrers")
    user.groups.add(batch_transferrers_group)
    return user


@pytest.mark.django_db
def test_user_must_be_logged_in_to_access_view(client):
    response = client.get(reverse("batch_transfer_job_create"))
    assert response.status_code == 302
    response = client.post(reverse("batch_transfer_job_create"))
    assert response.status_code == 302


def test_user_must_have_permission_to_access_view(client, user_without_permission):
    client.force_login(user_without_permission)
    response = client.get(reverse("batch_transfer_job_create"))
    assert response.status_code == 403
    response = client.post(reverse("batch_transfer_job_create"))
    assert response.status_code == 403


def test_logged_in_user_with_permission_can_access_form(client, user_with_permission):
    client.force_login(user_with_permission)
    response = client.get(reverse("batch_transfer_job_create"))
    assert response.status_code == 200
    assertTemplateUsed(response, "batch_transfer/batch_transfer_job_form.html")


@patch("adit.batch_transfer.tasks.batch_transfer.delay")
def test_batch_job_created_and_enqueued_with_auto_verify(
    batch_transfer_delay_mock, client, user_with_permission, settings, form_data
):
    client.force_login(user_with_permission)
    settings.BATCH_TRANSFER_UNVERIFIED = True
    client.post(reverse("batch_transfer_job_create"), form_data)
    job = BatchTransferJob.objects.first()
    assert job.requests.count() == 3
    batch_transfer_delay_mock.assert_called_once_with(job.id)


@patch("adit.batch_transfer.tasks.batch_transfer.delay")
def test_batch_job_created_and_not_enqueued_without_auto_verify(
    batch_transfer_delay_mock, client, user_with_permission, settings, form_data
):
    client.force_login(user_with_permission)
    settings.BATCH_TRANSFER_UNVERIFIED = False
    client.post(reverse("batch_transfer_job_create"), form_data)
    job = BatchTransferJob.objects.first()
    assert job.requests.count() == 3
    batch_transfer_delay_mock.assert_not_called()


def test_job_cant_be_created_with_missing_fields(
    client, user_with_permission, form_data
):
    client.force_login(user_with_permission)
    for key_to_exclude in form_data:
        invalid_form_data = form_data.copy()
        del invalid_form_data[key_to_exclude]
        response = client.post(reverse("batch_transfer_job_create"), invalid_form_data)
        assert len(response.context["form"].errors) > 0
        assert BatchTransferJob.objects.first() is None
