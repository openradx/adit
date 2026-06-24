"""Authorization-negative tests for the DICOMweb REST API.

These tests assert the auth/permission layer of the QIDO-RS, WADO-RS and STOW-RS
endpoints (`adit/dicom_web/views.py`). They do NOT require a live PACS: the
401/403/404 authorization decisions all happen before any DICOM network
operation is attempted (and for the "granted access" cases the network layer is
stubbed, see ``stub_dicom_network``).

Behavior under test (as implemented in the working tree):
* Authentication: ``RestTokenAuthentication``. A missing or invalid token raises
  ``AuthenticationFailed``, which DRF renders as 401 (the auth class defines
  ``authenticate_header``).
* Server scoping: ``WebDicomAPIView._get_dicom_server`` looks the server up in
  ``DicomServer.objects.accessible_by_user(user, access_type, all_groups=True)``
  and raises ``NotFound`` (404) when the user's groups have no matching access.
  So "valid token but no access" yields 404 (not 403).

These views are async (adrf ``AsyncApiView``). They must be exercised with
Django's ``AsyncClient``: driving them with the synchronous test ``Client``
deadlocks on the second request in a thread (asgiref ``async_to_sync``
current-thread-executor reentrancy), which is a test-harness limitation, not an
application bug.

Known gap (see module-level TODOs in views.py): the per-operation permissions
``can_query`` / ``can_retrieve`` / ``can_store`` are not enforced. Tests
asserting that a user with server access but without the specific operation
permission is denied are therefore marked ``xfail``.
"""

from unittest.mock import patch

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from adit_radis_shared.token_authentication.models import Token
from asgiref.sync import sync_to_async
from django.test import AsyncClient
from django.urls import reverse

from adit.core.factories import DicomServerFactory, DicomWebServerFactory
from adit.core.utils.auth_utils import grant_access

# Content type STOW-RS requires; sending it lets execution reach the
# server-access check instead of short-circuiting on UnsupportedMediaType (415).
STOW_CONTENT_TYPE = "multipart/related; type=application/dicom; boundary=adittest"

STUDY_UID = "1.2.3.4.5"


def _auth(token_string: str) -> dict:
    """Return a ``headers=`` mapping for AsyncClient carrying the auth token.

    NOTE: AsyncClient does not honor the ``HTTP_AUTHORIZATION`` extra-kwarg form
    that the sync test Client accepts; the header must be passed via ``headers=``
    (Django maps it to ``request.META["HTTP_AUTHORIZATION"]``, which
    ``RestTokenAuthentication`` reads).
    """
    return {"authorization": f"Token {token_string}"}


def _qido_url(ae_title: str) -> str:
    return reverse("qido_rs-studies", args=[ae_title])


def _wado_url(ae_title: str) -> str:
    return reverse("wado_rs-study_with_study_uid", args=[ae_title, STUDY_UID])


def _stow_url(ae_title: str) -> str:
    return reverse("stow_rs-series", args=[ae_title])


# --- async-safe setup helpers (ORM access must go through sync_to_async) -----


@sync_to_async
def create_server():
    return DicomServerFactory.create()


@sync_to_async
def create_web_server():
    return DicomWebServerFactory.create()


@sync_to_async
def create_group():
    return GroupFactory.create()


@sync_to_async
def grant(group, server, *, source=False, destination=False):
    grant_access(group, server, source=source, destination=destination)


@sync_to_async
def create_user_with_token():
    """User in a single group (no DICOM access granted yet) + a valid token."""
    user = UserFactory.create()
    group = GroupFactory.create()
    add_user_to_group(user, group)
    _, token_string = Token.objects.create_token(user, "", None)
    return user, group, token_string


@sync_to_async
def create_user_in_two_groups():
    """User whose *active* group differs from the group used to grant access."""
    user = UserFactory.create()
    active_group = GroupFactory.create()
    other_group = GroupFactory.create()
    add_user_to_group(user, active_group)  # sets active_group on first add
    user.groups.add(other_group)
    _, token_string = Token.objects.create_token(user, "", None)
    return user, other_group, token_string


async def _empty_async_iter(*args, **kwargs):
    """Async generator that yields nothing (stubs wado_retrieve / the STOW body
    parser)."""
    return
    yield  # pragma: no cover - makes this an async generator


@pytest.fixture
def stub_dicom_network():
    """Stub out the DICOM network / request-body layer of the dicom_web views.

    The authorization checks (401/403/404) all run *before* these functions do
    their work, so stubbing them lets us assert that a request got *past* the
    auth/permission layer without needing a live PACS (the factory servers point
    at random, unroutable hosts that would otherwise hang until TCP timeout) and
    without having to craft a valid multipart/related DICOM body for STOW.
    """

    async def fake_qido_find(*args, **kwargs):
        return []

    with (
        patch("adit.dicom_web.views.qido_find", new=fake_qido_find),
        patch("adit.dicom_web.views.wado_retrieve", new=_empty_async_iter),
        # STOW body parser -> yield no datasets, so the view skips stow_store and
        # returns an (empty) success result instead of failing on body parsing.
        patch("adit.dicom_web.views.parse_request_in_chunks", new=_empty_async_iter),
    ):
        yield


# ---------------------------------------------------------------------------
# 1. No / invalid token -> 401
# ---------------------------------------------------------------------------


class TestUnauthenticatedRejected:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_qido_without_token_returns_401(self):
        server = await create_server()
        response = await AsyncClient().get(_qido_url(server.ae_title))
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_wado_without_token_returns_401(self):
        server = await create_server()
        response = await AsyncClient().get(_wado_url(server.ae_title))
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_stow_without_token_returns_401(self):
        server = await create_server()
        response = await AsyncClient().post(
            _stow_url(server.ae_title), content_type=STOW_CONTENT_TYPE
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_qido_with_invalid_token_returns_401(self):
        server = await create_server()
        response = await AsyncClient().get(
            _qido_url(server.ae_title), headers=_auth("not-a-real-token")
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_wado_with_invalid_token_returns_401(self):
        server = await create_server()
        response = await AsyncClient().get(
            _wado_url(server.ae_title), headers=_auth("not-a-real-token")
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_stow_with_invalid_token_returns_401(self):
        server = await create_server()
        response = await AsyncClient().post(
            _stow_url(server.ae_title),
            content_type=STOW_CONTENT_TYPE,
            headers=_auth("not-a-real-token"),
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2. Valid token but user's group has NO access to the target server.
#    The view resolves the server via accessible_by_user and raises NotFound,
#    so the observed status is 404 (not 403).
# ---------------------------------------------------------------------------


class TestNoServerAccessRejected:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_qido_without_server_access_returns_404(self):
        _, _, token = await create_user_with_token()
        # Server exists but is granted to a *different* group.
        server = await create_server()
        other_group = await create_group()
        await grant(other_group, server, source=True)

        response = await AsyncClient().get(_qido_url(server.ae_title), headers=_auth(token))
        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_wado_without_server_access_returns_404(self):
        _, _, token = await create_user_with_token()
        server = await create_web_server()
        other_group = await create_group()
        await grant(other_group, server, source=True)

        response = await AsyncClient().get(_wado_url(server.ae_title), headers=_auth(token))
        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_stow_without_server_access_returns_404(self):
        _, _, token = await create_user_with_token()
        server = await create_server()
        other_group = await create_group()
        await grant(other_group, server, destination=True)

        response = await AsyncClient().post(
            _stow_url(server.ae_title),
            content_type=STOW_CONTENT_TYPE,
            headers=_auth(token),
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_qido_source_access_only_does_not_grant_other_server(self):
        """Access to one server must not authorize a different server."""
        _, group, token = await create_user_with_token()
        granted = await create_server()
        await grant(group, granted, source=True)
        forbidden = await create_server()

        response = await AsyncClient().get(_qido_url(forbidden.ae_title), headers=_auth(token))
        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_destination_access_does_not_grant_source_for_query(self):
        """A server granted only as destination must not be queryable (source)."""
        _, group, token = await create_user_with_token()
        server = await create_server()
        await grant(group, server, source=False, destination=True)

        response = await AsyncClient().get(_qido_url(server.ae_title), headers=_auth(token))
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3. Valid token + granted access -> request passes the auth/permission layer.
#    The DICOM network layer is stubbed (see stub_dicom_network), since these
#    factory servers point at unroutable hosts. The stub is only reached if the
#    request already passed authz, so we assert the status is NOT 401/403/404.
# ---------------------------------------------------------------------------

NOT_AUTHORIZED_STATUSES = {401, 403, 404}


class TestGrantedAccessPassesAuthLayer:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_qido_with_source_access_passes_auth_layer(self, stub_dicom_network):
        _, group, token = await create_user_with_token()
        server = await create_server()
        await grant(group, server, source=True)

        response = await AsyncClient().get(_qido_url(server.ae_title), headers=_auth(token))
        # Got past authz; the (stubbed) query then succeeds with an empty result.
        assert response.status_code not in NOT_AUTHORIZED_STATUSES

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_wado_with_source_access_passes_auth_layer(self, stub_dicom_network):
        # WADO requires a server with WADO-capable support flags.
        _, group, token = await create_user_with_token()
        server = await create_web_server()
        await grant(group, server, source=True)

        # Ask for the multipart DICOM renderer (what a real WADO-RS client sends)
        # so content negotiation selects the streaming renderer that matches the
        # stubbed (empty) image iterator.
        headers = {**_auth(token), "accept": "multipart/related; type=application/dicom"}
        response = await AsyncClient().get(_wado_url(server.ae_title), headers=headers)
        assert response.status_code not in NOT_AUTHORIZED_STATUSES

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_stow_with_destination_access_passes_auth_layer(self, stub_dicom_network):
        _, group, token = await create_user_with_token()
        server = await create_server()
        await grant(group, server, destination=True)

        response = await AsyncClient().post(
            _stow_url(server.ae_title),
            content_type=STOW_CONTENT_TYPE,
            headers=_auth(token),
        )
        assert response.status_code not in NOT_AUTHORIZED_STATUSES

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_access_granted_via_non_active_group(self, stub_dicom_network):
        """The view uses all_groups=True, so access via any of the user's groups
        (not only the active one) must authorize the request."""
        _, other_group, token = await create_user_in_two_groups()
        server = await create_server()
        # Grant only via the non-active group.
        await grant(other_group, server, source=True)

        response = await AsyncClient().get(_qido_url(server.ae_title), headers=_auth(token))
        assert response.status_code not in NOT_AUTHORIZED_STATUSES


# ---------------------------------------------------------------------------
# KNOWN GAP: per-operation permissions can_query / can_retrieve / can_store
# are not enforced (TODOs in views.py). A user with server access but WITHOUT
# the specific operation permission is currently NOT denied. These xfail tests
# document the expected (but unimplemented) behavior. The network layer is
# stubbed so the assertion fails cleanly (200 != 403) instead of the request
# proceeding to a (non-existent) PACS.
# ---------------------------------------------------------------------------


class TestPerOperationPermissionsNotEnforced:
    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @pytest.mark.xfail(
        reason="can_query not enforced yet - dicom_web/views.py TODO",
        strict=True,
    )
    async def test_qido_denied_without_can_query_permission(self, stub_dicom_network):
        # Group has server source access but NOT the can_query permission.
        _, group, token = await create_user_with_token()
        server = await create_server()
        await grant(group, server, source=True)

        response = await AsyncClient().get(_qido_url(server.ae_title), headers=_auth(token))
        # Expected once enforced: forbidden. Currently passes authz -> xfail.
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @pytest.mark.xfail(
        reason="can_retrieve not enforced yet - dicom_web/views.py TODO",
        strict=True,
    )
    async def test_wado_denied_without_can_retrieve_permission(self, stub_dicom_network):
        _, group, token = await create_user_with_token()
        server = await create_web_server()
        await grant(group, server, source=True)

        response = await AsyncClient().get(_wado_url(server.ae_title), headers=_auth(token))
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    @pytest.mark.xfail(
        reason="can_store not enforced yet - dicom_web/views.py TODO",
        strict=True,
    )
    async def test_stow_denied_without_can_store_permission(self, stub_dicom_network):
        _, group, token = await create_user_with_token()
        server = await create_server()
        await grant(group, server, destination=True)

        response = await AsyncClient().post(
            _stow_url(server.ae_title),
            content_type=STOW_CONTENT_TYPE,
            headers=_auth(token),
        )
        assert response.status_code == 403
