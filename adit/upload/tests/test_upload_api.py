"""Tests for the DICOM ingestion endpoint ``upload_api_view`` (upload/views.py).

These exercise the auth/permission gates and the bad/missing-dataset error
responses. No live PACS is needed: every assertion here is about a decision the
view makes *before* any DICOM network operation (the operator is never reached on
these paths, or ``read_dataset`` is stubbed).

``upload_api_view`` is an async view, driven here with Django's ``AsyncClient``
(the synchronous test ``Client`` deadlocks an async view whose body awaits
``sync_to_async``/native-async ORM). The repo's
dicom_web/tests/test_authorization.py documents the same constraint.

KNOWN HARNESS-LEVEL ORDERING ISSUE (flagged): the app always applies
``nest_asyncio`` (adit/conftest.py). Running these session-auth ``AsyncClient``
tests leaves event-loop/connection state in the process that wedges the
*pre-existing*
selective_transfer/tests/test_download.py::test_download_with_invalid_server_returns_404,
which drives an async view through a bare ``async_to_sync(view)()`` -- it then
deadlocks (pytest-timeout fires at 60 s). The same full ``pytest`` run also fails
the unrelated, pre-existing ProcessPool tests in core/tests/test_tasks.py (those
fail even run alone). These upload tests pass on their own
(``pytest adit/upload/tests/test_upload_api.py`` -> 5 passed); the repo's
existing async tests use the same ``AsyncClient`` pattern. No clean test-side
teardown was found that both releases the leaked state and preserves the
non-transactional sync tests, so the interaction is documented rather than
papered over.
"""

import io

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from asgiref.sync import sync_to_async
from django.test import AsyncClient
from django.urls import reverse

from adit.core.factories import DicomServerFactory
from adit.core.utils.auth_utils import grant_access
from adit.upload.utils.testing_helpers import create_upload_group


def _data_upload_url(node_id) -> str:
    return reverse("data_upload", kwargs={"node_id": node_id})


@sync_to_async
def _setup(*, with_permission: bool, grant_destination: bool):
    """Async-safe ORM setup: build a user and a destination server."""
    user = UserFactory.create(is_active=True)
    if with_permission:
        add_user_to_group(user, create_upload_group())
    server = DicomServerFactory.create()
    if grant_destination:
        # grant_destination implies the user is in a group we can grant to.
        grant_access(user.active_group, server, destination=True)
    return user, server


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_upload_api_non_post_returns_405():
    user, server = await _setup(with_permission=True, grant_destination=False)
    client = AsyncClient()
    await client.aforce_login(user)

    response = await client.get(_data_upload_url(server.pk))

    assert response.status_code == 405


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_upload_api_without_permission_is_forbidden():
    # A logged-in user lacking "upload.can_upload_data" must be denied (first gate),
    # before any destination lookup happens.
    user, server = await _setup(with_permission=False, grant_destination=False)
    client = AsyncClient()
    await client.aforce_login(user)

    response = await client.post(_data_upload_url(server.pk))

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_upload_api_destination_not_accessible_is_forbidden():
    # The user has the upload permission, but the destination server is not granted
    # to the user's group as a destination -> second PermissionDenied gate.
    user, server = await _setup(with_permission=True, grant_destination=False)
    client = AsyncClient()
    await client.aforce_login(user)

    response = await client.post(
        _data_upload_url(server.pk),
        data={"dataset": io.BytesIO(b"whatever")},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_upload_api_missing_dataset_returns_400():
    # Permitted user, accessible destination, but no file uploaded at all.
    user, server = await _setup(with_permission=True, grant_destination=True)
    client = AsyncClient()
    await client.aforce_login(user)

    response = await client.post(_data_upload_url(server.pk))

    assert response.status_code == 400
    assert response.content == b"No data received"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_upload_api_invalid_dataset_returns_400(mocker):
    # Permitted user, accessible destination, but parsing the uploaded "dataset"
    # fails -> the view catches the exception and returns 400 "Invalid dataset".
    #
    # NOTE: read_dataset() uses pydicom's dcmread(force=True), which parses almost
    # any byte string into a (junk) Dataset *and* defers value parsing lazily, so
    # supplying raw garbage does NOT make read_dataset raise at call time (it would
    # instead reach operator.upload_images and try a real C-STORE). We therefore
    # drive the error branch directly by making read_dataset raise, which is the
    # condition the view's try/except is written to handle.
    user, server = await _setup(with_permission=True, grant_destination=True)
    client = AsyncClient()
    await client.aforce_login(user)

    mocker.patch(
        "adit.upload.views.read_dataset",
        side_effect=ValueError("cannot parse DICOM"),
    )

    bad_file = io.BytesIO(b"not a dicom file")
    bad_file.name = "bad.dcm"

    response = await client.post(
        _data_upload_url(server.pk),
        data={"dataset": bad_file},
    )

    assert response.status_code == 400
    assert response.content == b"Invalid dataset"
