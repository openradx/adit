import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomNodeGroupAccess


@pytest.mark.django_db
def test_dicom_explorer_form_view(client):
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    response = client.get("/dicom-explorer/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_dicom_explorer_form_view_with_server_redirect(client):
    group = GroupFactory.create()
    user = UserFactory.create(is_active=True)
    user.groups.add(group)
    user.active_group = group
    user.save()
    client.force_login(user)
    server = DicomServerFactory.create()

    DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)
    response = client.get(f"/dicom-explorer/?server={server.pk}")
    assert response.status_code == 302
