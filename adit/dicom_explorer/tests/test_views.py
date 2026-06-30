from typing import cast

import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.utils.testing_helpers import add_permission
from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.test import AsyncClient
from pydicom import Dataset
from pytest_mock import MockerFixture

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomNodeGroupAccess
from adit.core.utils.dicom_dataset import ResultDataset

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
    assert "/accounts/login/" in response["Location"]
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


# ---------------------------------------------------------------------------
# Helpers for the render-branch tests below.
#
# The render_* functions in views.py branch on the *number* of results returned
# by DicomDataCollector (0 / 1 / many) and on the resolved URL name. To exercise
# those branches reliably without depending on the completeness of the page
# templates (which read many DICOM tags), we mock ``render`` at the views module
# level and capture (template_name, context). The collector is mocked at the
# boundary, so no live PACS is contacted.
# ---------------------------------------------------------------------------


def _result(**attrs) -> ResultDataset:
    ds = Dataset()
    for key, value in attrs.items():
        setattr(ds, key, value)
    return ResultDataset(ds)


def _patch_render(mocker: MockerFixture):
    """Patch views.render to capture the rendered template + context.

    Returns the mock; ``mock.call_args`` exposes (request, template_name, context).
    """
    return mocker.patch(
        "adit.dicom_explorer.views.render",
        side_effect=lambda request, template, context=None: HttpResponse(
            f"rendered:{template}"
        ),
    )


@sync_to_async
def _setup_permitted_user_and_server():
    user, group = _make_user_with_group()
    _grant_query_permission(group)
    server = DicomServerFactory.create()
    DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)
    return user, server


def _rendered_template(render_mock) -> str:
    return render_mock.call_args.args[1]


def _rendered_context(render_mock) -> dict:
    return render_mock.call_args.args[2]


# ---------------------------------------------------------------------------
# form view: redirect branches (views.py:35-51)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_view_invalid_form_rerenders(client):
    """A bound-but-invalid form re-renders the query form (views.py:27-28)."""
    user = UserFactory.create(is_active=True)
    client.force_login(user)
    # A backslash in patient_id fails id validation; server is also missing/invalid.
    response = client.get("/dicom-explorer/?patient_id=bad%5Cvalue&query=Query")
    assert response.status_code == 200


@pytest.mark.django_db
def test_form_view_patient_id_redirects_to_patient_detail(client):
    group = GroupFactory.create()
    user = UserFactory.create(is_active=True)
    user.groups.add(group)
    user.active_group = group
    user.save()
    client.force_login(user)
    server = DicomServerFactory.create()
    DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)

    response = client.get(f"/dicom-explorer/?server={server.pk}&patient_id=PAT001")
    assert response.status_code == 302
    # Redirects to the patient detail resource (views.py:38-39).
    assert f"/servers/{server.pk}/patients/PAT001" in response.url


@pytest.mark.django_db
def test_form_view_accession_number_redirects_with_query_params(client):
    group = GroupFactory.create()
    user = UserFactory.create(is_active=True)
    user.groups.add(group)
    user.active_group = group
    user.save()
    client.force_login(user)
    server = DicomServerFactory.create()
    DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)

    response = client.get(
        f"/dicom-explorer/?server={server.pk}&patient_id=PAT001&accession_number=ACC1"
    )
    assert response.status_code == 302
    # Redirects to the patient query resource with AccessionNumber + PatientID
    # encoded as query parameters (views.py:41-48).
    assert f"/servers/{server.pk}/patients/" in response.url
    assert "AccessionNumber=ACC1" in response.url
    assert "PatientID=PAT001" in response.url


# ---------------------------------------------------------------------------
# resources view: invalid id rejection + timeout (views.py:63-85)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resources_view_invalid_patient_id_short_circuits(mocker: MockerFixture):
    """An invalid Patient ID must short-circuit before any PACS query.

    dicom_explorer_resources_view validates the id (views.py:63-64) and returns the
    render_error() response, so the DicomDataCollector is never constructed.
    """
    user, server = await _setup_permitted_user_and_server()
    client = AsyncClient()
    await client.aforce_login(user)

    collector_mock = mocker.patch("adit.dicom_explorer.views.DicomDataCollector")
    collector_mock.return_value.collect_patients.return_value = []

    # "*" is an invalid (wildcard) character for a Patient ID.
    response = await client.get(f"/dicom-explorer/servers/{server.pk}/patients/%2A/")

    assert response.status_code == 200
    # The guard short-circuits: no PACS query is attempted for an invalid id.
    collector_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resources_view_invalid_patient_id_should_return_error(mocker: MockerFixture):
    user, server = await _setup_permitted_user_and_server()
    client = AsyncClient()
    await client.aforce_login(user)

    collector_mock = mocker.patch("adit.dicom_explorer.views.DicomDataCollector")
    collector_mock.return_value.collect_patients.return_value = []

    response = await client.get(f"/dicom-explorer/servers/{server.pk}/patients/%2A/")

    # The invalid-id guard renders the error page and does not query the PACS.
    assert b"Invalid Patient ID" in response.content
    collector_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resources_view_timeout_renders_error(mocker: MockerFixture):
    """If the PACS query exceeds DICOM_EXPLORER_RESPONSE_TIMEOUT the view renders a
    timeout error (views.py:84-85)."""
    user, server = await _setup_permitted_user_and_server()
    client = AsyncClient()
    await client.aforce_login(user)

    # Force asyncio.wait_for to raise TimeoutError regardless of the real work.
    async def fake_wait_for(future, timeout):
        # Cancel the underlying future to avoid a dangling executor task.
        if hasattr(future, "cancel"):
            future.cancel()
        raise TimeoutError()

    mocker.patch("adit.dicom_explorer.views.asyncio.wait_for", side_effect=fake_wait_for)

    response = await client.get(f"/dicom-explorer/servers/{server.pk}/")
    assert response.status_code == 200
    assert b"timed out" in response.content


# ---------------------------------------------------------------------------
# render_query_result routing + render_* branches (views.py:103-360)
#
# These call the sync render_query_result helpers directly (mocking render and
# the collector), which lets us drive every URL-name branch and every
# 0/1/many-result branch without the AsyncClient/executor indirection.
# ---------------------------------------------------------------------------


def _make_request(
    mocker: MockerFixture, user, path: str, get_params: dict | None = None
) -> AuthenticatedHttpRequest:
    from django.test import RequestFactory

    request = RequestFactory().get(path, data=get_params or {})
    request.user = user
    return cast(AuthenticatedHttpRequest, request)


class TestRenderServerQuery:
    @pytest.mark.django_db
    def test_server_query_lists_accessible_servers(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        render_mock = _patch_render(mocker)

        request = _make_request(mocker, user, "/dicom-explorer/servers/")
        response = views.render_server_query(request, {})

        assert response.status_code == 200
        assert _rendered_template(render_mock) == "dicom_explorer/server_query.html"
        assert "servers" in _rendered_context(render_mock)


class TestRenderServerDetail:
    @pytest.mark.django_db
    def test_server_detail_renders(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)

        request = _make_request(mocker, user, f"/dicom-explorer/servers/{server.pk}/")
        response = views.render_server_detail(request, server)

        assert response.status_code == 200
        assert _rendered_template(render_mock) == "dicom_explorer/server_detail.html"
        assert _rendered_context(render_mock)["server"] is server


class TestRenderPatientQuery:
    @pytest.mark.django_db
    def test_patient_query_below_limit(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]

        request = _make_request(mocker, user, "/x", {"PatientID": "PAT001"})
        response = views.render_patient_query(request, server, {"PatientID": "PAT001"})

        assert response.status_code == 200
        ctx = _rendered_context(render_mock)
        assert _rendered_template(render_mock) == "dicom_explorer/patient_query.html"
        assert ctx["max_results_reached"] is False
        assert len(ctx["patients"]) == 1

    @pytest.mark.django_db
    def test_patient_query_at_limit_sets_flag(self, mocker: MockerFixture):
        from django.conf import settings

        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        # Return exactly the limit -> max_results_reached True (views.py:186).
        limit = settings.DICOM_EXPLORER_RESULT_LIMIT
        collector.collect_patients.return_value = [
            _result(PatientID=str(i)) for i in range(limit)
        ]

        request = _make_request(mocker, user, "/x")
        views.render_patient_query(request, server, {})

        assert _rendered_context(render_mock)["max_results_reached"] is True


class TestRenderPatientDetail:
    @pytest.mark.django_db
    def test_patient_detail_single(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]
        collector.collect_studies.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_patient_detail(request, server, "PAT001")

        assert _rendered_template(render_mock) == "dicom_explorer/patient_detail.html"

    @pytest.mark.django_db
    def test_patient_detail_none_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_patients.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_patient_detail(request, server, "PAT001")

        # 0 patients -> error_message template (views.py:205-206).
        assert _rendered_template(render_mock) == "dicom_explorer/error_message.html"
        assert "No patient found" in _rendered_context(render_mock)["error_message"]

    @pytest.mark.django_db
    def test_patient_detail_multiple_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_patients.return_value = [
            _result(PatientID="PAT001"),
            _result(PatientID="PAT001"),
        ]

        request = _make_request(mocker, user, "/x")
        views.render_patient_detail(request, server, "PAT001")

        # >1 patients -> error (views.py:208-209).
        assert _rendered_template(render_mock) == "dicom_explorer/error_message.html"
        assert "Multiple patients found" in _rendered_context(render_mock)["error_message"]


class TestRenderStudyQuery:
    @pytest.mark.django_db
    def test_study_query(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [_result(StudyInstanceUID="1.2.3")]

        request = _make_request(mocker, user, "/x")
        views.render_study_query(request, server, {})

        assert _rendered_template(render_mock) == "dicom_explorer/study_query.html"
        assert _rendered_context(render_mock)["max_results_reached"] is False


class TestRenderStudyDetail:
    @pytest.mark.django_db
    def test_study_detail_single(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001")
        ]
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]
        collector.collect_series.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_study_detail(request, server, "1.2.3")

        assert _rendered_template(render_mock) == "dicom_explorer/study_detail.html"

    @pytest.mark.django_db
    def test_study_detail_none_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_study_detail(request, server, "1.2.3")

        assert _rendered_template(render_mock) == "dicom_explorer/error_message.html"
        assert "No study found" in _rendered_context(render_mock)["error_message"]

    @pytest.mark.django_db
    def test_study_detail_multiple_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001"),
            _result(StudyInstanceUID="1.2.3", PatientID="PAT002"),
        ]

        request = _make_request(mocker, user, "/x")
        views.render_study_detail(request, server, "1.2.3")

        assert "Multiple studies found" in _rendered_context(render_mock)["error_message"]

    @pytest.mark.django_db
    def test_study_detail_multiple_patients_raises(self, mocker: MockerFixture):
        """The 'should never happen' patient ambiguity for a found study is an
        AssertionError (views.py:254-258)."""
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001")
        ]
        collector.collect_patients.return_value = [
            _result(PatientID="PAT001"),
            _result(PatientID="PAT001"),
        ]

        request = _make_request(mocker, user, "/x")
        with pytest.raises(AssertionError, match="Multiple patients found"):
            views.render_study_detail(request, server, "1.2.3")


class TestRenderSeriesQuery:
    @pytest.mark.django_db
    def test_series_query_single_study(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001")
        ]
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]
        collector.collect_series.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_series_query(request, server, "1.2.3", {})

        assert _rendered_template(render_mock) == "dicom_explorer/series_query.html"

    @pytest.mark.django_db
    def test_series_query_no_study_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_series_query(request, server, "1.2.3", {})

        assert "No study found" in _rendered_context(render_mock)["error_message"]


class TestRenderSeriesDetail:
    @pytest.mark.django_db
    def test_series_detail_single(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001")
        ]
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]
        collector.collect_series.return_value = [_result(SeriesInstanceUID="1.2.3.4")]

        request = _make_request(mocker, user, "/x")
        views.render_series_detail(request, server, "1.2.3", "1.2.3.4")

        assert _rendered_template(render_mock) == "dicom_explorer/series_detail.html"

    @pytest.mark.django_db
    def test_series_detail_none_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001")
        ]
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]
        collector.collect_series.return_value = []

        request = _make_request(mocker, user, "/x")
        views.render_series_detail(request, server, "1.2.3", "1.2.3.4")

        # 0 series -> error (views.py:342-349).
        assert "No series found" in _rendered_context(render_mock)["error_message"]

    @pytest.mark.django_db
    def test_series_detail_multiple_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()
        render_mock = _patch_render(mocker)
        collector = mocker.patch("adit.dicom_explorer.views.DicomDataCollector").return_value
        collector.collect_studies.return_value = [
            _result(StudyInstanceUID="1.2.3", PatientID="PAT001")
        ]
        collector.collect_patients.return_value = [_result(PatientID="PAT001")]
        collector.collect_series.return_value = [
            _result(SeriesInstanceUID="1.2.3.4"),
            _result(SeriesInstanceUID="1.2.3.4"),
        ]

        request = _make_request(mocker, user, "/x")
        views.render_series_detail(request, server, "1.2.3", "1.2.3.4")

        assert "Multiple series found" in _rendered_context(render_mock)["error_message"]


# ---------------------------------------------------------------------------
# render_query_result: server-scope error + URL-name dispatch (views.py:120-157)
# ---------------------------------------------------------------------------


class TestRenderQueryResultDispatch:
    @pytest.mark.django_db
    def test_inaccessible_server_renders_error(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, _ = _make_user_with_group()
        server = DicomServerFactory.create()  # not granted to the user's group
        render_mock = _patch_render(mocker)
        mocker.patch("adit.dicom_explorer.views.DicomDataCollector")

        # resolve() needs a real URL; use the server_detail route.
        request = _make_request(mocker, user, f"/dicom-explorer/servers/{server.pk}/")
        views.render_query_result(request, server_id=str(server.pk))

        # Server not accessible by user -> "Invalid DICOM server." (views.py:127-128).
        assert "Invalid DICOM server." in _rendered_context(render_mock)["error_message"]

    @pytest.mark.django_db
    def test_server_query_url_skips_server_lookup(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, group = _make_user_with_group()
        server = DicomServerFactory.create()
        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)
        render_mock = _patch_render(mocker)
        mocker.patch("adit.dicom_explorer.views.DicomDataCollector")

        # The server_query URL name routes before the server lookup (views.py:122-123).
        request = _make_request(mocker, user, "/dicom-explorer/servers/")
        views.render_query_result(request)

        assert _rendered_template(render_mock) == "dicom_explorer/server_query.html"


# ---------------------------------------------------------------------------
# is_valid_id unit tests (views.py:88-96)
# ---------------------------------------------------------------------------


class TestIsValidId:
    def test_accepts_plain_id(self):
        from adit.dicom_explorer.views import is_valid_id

        assert is_valid_id("1.2.840.113619") is True

    @pytest.mark.parametrize(
        "bad",
        [
            "with\\backslash",
            "with\ncontrol",
            "with\rcontrol",
            "with\fcontrol",
            "with*wildcard",
            "with?wildcard",
        ],
    )
    def test_rejects_invalid_chars(self, bad):
        from adit.dicom_explorer.views import is_valid_id

        assert is_valid_id(bad) is False


# ---------------------------------------------------------------------------
# render_query_result: full URL-name dispatch (views.py:130-157)
#
# Drive every url_name branch of the dispatcher. The render_* sub-functions are
# stubbed so the test focuses on the routing decision (which sub-function each
# url_name selects). The server lookup is satisfied with a granted server.
# ---------------------------------------------------------------------------


class TestRenderQueryResultRouting:
    def _setup(self, mocker: MockerFixture):
        user, group = _make_user_with_group()
        server = DicomServerFactory.create()
        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)
        # Stub each render_* so we can detect which one the dispatcher picked.
        stubs = {}
        for name in (
            "render_server_detail",
            "render_patient_query",
            "render_patient_detail",
            "render_study_query",
            "render_study_detail",
            "render_series_query",
            "render_series_detail",
        ):
            stubs[name] = mocker.patch(
                f"adit.dicom_explorer.views.{name}", return_value=HttpResponse(name)
            )
        return user, server, stubs

    @pytest.mark.django_db
    def test_routes_server_detail(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(mocker, user, f"/dicom-explorer/servers/{server.pk}/")
        views.render_query_result(request, server_id=str(server.pk))
        stubs["render_server_detail"].assert_called_once()

    @pytest.mark.django_db
    def test_routes_patient_query(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(
            mocker, user, f"/dicom-explorer/servers/{server.pk}/patients/"
        )
        views.render_query_result(request, server_id=str(server.pk))
        stubs["render_patient_query"].assert_called_once()

    @pytest.mark.django_db
    def test_routes_patient_detail(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(
            mocker, user, f"/dicom-explorer/servers/{server.pk}/patients/PAT001/"
        )
        views.render_query_result(request, server_id=str(server.pk), patient_id="PAT001")
        stubs["render_patient_detail"].assert_called_once()

    @pytest.mark.django_db
    def test_routes_study_query(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(
            mocker, user, f"/dicom-explorer/servers/{server.pk}/studies/"
        )
        views.render_query_result(request, server_id=str(server.pk))
        stubs["render_study_query"].assert_called_once()

    @pytest.mark.django_db
    def test_routes_study_detail(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(
            mocker, user, f"/dicom-explorer/servers/{server.pk}/studies/1.2.3/"
        )
        views.render_query_result(request, server_id=str(server.pk), study_uid="1.2.3")
        stubs["render_study_detail"].assert_called_once()

    @pytest.mark.django_db
    def test_routes_series_query(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(
            mocker, user, f"/dicom-explorer/servers/{server.pk}/studies/1.2.3/series/"
        )
        views.render_query_result(request, server_id=str(server.pk), study_uid="1.2.3")
        stubs["render_series_query"].assert_called_once()

    @pytest.mark.django_db
    def test_routes_series_detail(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, stubs = self._setup(mocker)
        request = _make_request(
            mocker,
            user,
            f"/dicom-explorer/servers/{server.pk}/studies/1.2.3/series/1.2.3.4/",
        )
        views.render_query_result(
            request, server_id=str(server.pk), study_uid="1.2.3", series_uid="1.2.3.4"
        )
        stubs["render_series_detail"].assert_called_once()

    @pytest.mark.django_db
    def test_patient_detail_missing_patient_id_raises(self, mocker: MockerFixture):
        from adit.dicom_explorer import views

        user, server, _ = self._setup(mocker)
        request = _make_request(
            mocker, user, f"/dicom-explorer/servers/{server.pk}/patients/PAT001/"
        )
        # url resolves to patient_detail but patient_id arg is None -> AssertionError
        # (views.py:135-136).
        with pytest.raises(AssertionError, match="Missing patient ID"):
            views.render_query_result(request, server_id=str(server.pk), patient_id=None)
