import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission
from asgiref.sync import sync_to_async
from django.test import AsyncClient
from pytest_mock import MockerFixture

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomNodeGroupAccess

# `dicom_explorer_resources_view` is async (it offloads the blocking PACS query to
# an executor and awaits it). Like the dicom_web views, it must be exercised with
# Django's ``AsyncClient`` to avoid the ``async_to_sync`` reentrancy deadlock that
# the synchronous test ``Client`` triggers.


def _make_user_with_group(active: bool = True):
    group = GroupFactory.create()
    user = UserFactory.create(is_active=True)
    user.groups.add(group)
    if active:
        user.active_group = group
        user.save()
    return user, group


def _grant_query_permission(group) -> None:
    add_permission(group, "dicom_explorer", "query_dicom_server")


@sync_to_async
def _setup_user_and_server(*, with_permission: bool, grant_source: bool):
    user, group = _make_user_with_group()
    if with_permission:
        _grant_query_permission(group)
    server = DicomServerFactory.create()
    if grant_source:
        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)
    return user, server


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


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resources_view_requires_query_permission(mocker: MockerFixture):
    # A user without the "dicom_explorer.query_dicom_server" permission must not be
    # able to reach the resources view. permission_required (without raise_exception)
    # redirects to the login page rather than returning 403.
    user, server = await _setup_user_and_server(with_permission=False, grant_source=True)
    client = AsyncClient()
    await client.aforce_login(user)

    collector_mock = mocker.patch("adit.dicom_explorer.views.DicomDataCollector")

    response = await client.get(
        f"/dicom-explorer/servers/{server.pk}/patients/?PatientID=1001"
    )

    assert response.status_code == 302
    assert "/accounts/login/" in response.url
    # No PACS query may be attempted when the permission gate blocks the request.
    collector_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resources_view_scopes_to_accessible_servers(mocker: MockerFixture):
    # A permitted user querying a server their active group cannot access as a source
    # must get the generic "Invalid DICOM server" error, and crucially the
    # DicomDataCollector (which would contact the PACS) must never be constructed.
    # Server exists but is NOT granted to the user's group -> out of scope.
    user, server = await _setup_user_and_server(with_permission=True, grant_source=False)
    client = AsyncClient()
    await client.aforce_login(user)

    collector_mock = mocker.patch("adit.dicom_explorer.views.DicomDataCollector")

    response = await client.get(
        f"/dicom-explorer/servers/{server.pk}/patients/?PatientID=1001"
    )

    assert response.status_code == 200
    assert b"Invalid DICOM server." in response.content
    collector_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resources_view_queries_accessible_server(mocker: MockerFixture):
    # Positive control: a permitted user querying a server their active group can
    # access as a source reaches the DicomDataCollector with that server.
    user, server = await _setup_user_and_server(with_permission=True, grant_source=True)
    client = AsyncClient()
    await client.aforce_login(user)

    collector_mock = mocker.patch("adit.dicom_explorer.views.DicomDataCollector")
    collector_mock.return_value.collect_patients.return_value = []

    response = await client.get(
        f"/dicom-explorer/servers/{server.pk}/patients/?PatientID=1001"
    )

    assert response.status_code == 200
    collector_mock.assert_called_once_with(server)
    collector_mock.return_value.collect_patients.assert_called_once()
