"""Integration tests for the selective-transfer WebSocket consumer.

These drive the real `SelectiveTransferConsumer` through Channels'
`WebsocketCommunicator` (the consumer's own ASGI application), so the full
message protocol, permission gating, form handling, and DB writes run for real.
Only the DICOM network boundary is mocked: `DicomOperator` (constructed inside
the consumer) is replaced so no live PACS / C-FIND is needed.

Covered:
  * connect() rejects an unauthenticated user (close code 4401) and accepts an
    authenticated, permitted user.
  * receive_json without the add-permission returns an access-denied message.
  * An invalid `action` is rejected with an error message.
  * A `query` action dispatches to `DicomOperator.find_studies` and streams the
    rendered results (the queried PatientID appears in the streamed HTML).
  * The non-staff "max 10 studies" guard rejects an over-limit transfer
    (no job is created); a staff user is allowed past the limit.
  * A valid `transfer` action creates the job + tasks and enqueues them
    (queued_job set on the task via Procrastinate).

Notes:
  * `send_query_response` is wrapped in `@debounce(wait_time=1)`, so the query
    result is delivered ~1s after the worker thread finishes; the relevant
    `receive_from` calls therefore use a generous timeout.
  * Tests are `transaction=True` because the consumer offloads the query to a
    `ThreadPoolExecutor` and the transfer path defers Procrastinate jobs — both
    cross the async/sync (and thread) boundary and need committed rows.
"""

from unittest.mock import MagicMock

import pytest
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.testing_helpers import add_permission, add_user_to_group
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, Group
from pydicom import Dataset

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.core.utils.dicom_dataset import ResultDataset
from adit.selective_transfer import consumers as consumers_module
from adit.selective_transfer.consumers import SelectiveTransferConsumer
from adit.selective_transfer.models import SelectiveTransferJob, SelectiveTransferTask

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _build_user_with_access(*, is_staff: bool = False) -> tuple[User, DicomServer, DicomServer]:
    """Create a user in a group that can add jobs, transfer unpseudonymized, and
    access a source server + a destination server. Returns (user, source, dest).
    """
    user = UserFactory.create(is_active=True, is_staff=is_staff)
    group = Group.objects.create(name=f"transfer-group-{user.pk}")
    add_user_to_group(user, group)
    add_permission(group, "selective_transfer", "add_selectivetransferjob")
    # Allow transferring without a pseudonym so the transfer form validates.
    add_permission(group, "selective_transfer", "can_transfer_unpseudonymized")

    source = DicomServerFactory.create()
    destination = DicomServerFactory.create()
    grant_access(group, source, source=True)
    grant_access(group, destination, destination=True)

    return user, source, destination


def _make_result_study(patient_id: str, study_uid: str) -> ResultDataset:
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientName = "Doe^John"
    ds.PatientBirthDate = "19800101"
    ds.StudyInstanceUID = study_uid
    ds.AccessionNumber = "ACC1"
    ds.StudyDate = "20200102"
    ds.StudyTime = "120000"
    ds.StudyDescription = "Test Study"
    ds.ModalitiesInStudy = ["CT"]
    ds.NumberOfStudyRelatedSeries = 1
    ds.NumberOfStudyRelatedInstances = 3
    return ResultDataset(ds)


def _query_payload(source: DicomServer, destination: DicomServer, **overrides) -> dict:
    payload = {
        "action": "query",
        "source": str(source.pk),
        "destination": str(destination.pk),
        "patient_id": "",
        "patient_name": "",
        "patient_birth_date": "",
        "study_date": "",
        "modality": "",
        "accession_number": "",
        "pseudonym": "",
        "trial_protocol_id": "",
        "trial_protocol_name": "",
        "archive_password": "",
    }
    payload.update(overrides)
    return payload


async def _connect(user) -> WebsocketCommunicator:
    communicator = WebsocketCommunicator(
        SelectiveTransferConsumer.as_asgi(), "/ws/selective-transfer"
    )
    communicator.scope["user"] = user
    return communicator


async def _drain(communicator: WebsocketCommunicator, *, timeout: float = 6.0) -> str:
    """Collect all currently-available text frames into one string."""
    collected: list[str] = []
    while True:
        try:
            collected.append(await communicator.receive_from(timeout=timeout))
        except BaseException:
            # TimeoutError ends the drain; CancelledError (BaseException in
            # py3.11+) can surface if the consumer's background task is cancelled.
            break
        # After the first frame, only wait briefly for further frames.
        timeout = 0.3
    return "".join(collected)


async def _safe_disconnect(communicator: WebsocketCommunicator) -> None:
    """Disconnect, tolerating the consumer cancelling an in-flight query task.

    The consumer offloads queries to a thread pool and a debounced timer; when a
    test disconnects while that work is still settling, Channels cancels the
    consumer task and `disconnect()` surfaces a CancelledError (a BaseException
    in py3.11+). That is teardown noise unrelated to the behaviour under test,
    so we swallow it.
    """
    try:
        await communicator.disconnect(timeout=5)
    except BaseException:
        pass


# ---------------------------------------------------------------------------
# Connect / auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_rejects_unauthenticated_user():
    communicator = await _connect(AnonymousUser())
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4401
    # A disconnect after a rejected connect is exercised separately by
    # test_disconnect_after_rejected_connect_is_safe.


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_rejects_when_no_user_in_scope():
    communicator = WebsocketCommunicator(
        SelectiveTransferConsumer.as_asgi(), "/ws/selective-transfer"
    )
    # No "user" key in scope at all.
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4401
    # See note in test_connect_rejects_unauthenticated_user re: no disconnect().


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_disconnect_after_rejected_connect_is_safe():
    """A disconnect following a rejected (unauthenticated) connect must not
    raise. connect() returns before accepting and never reaches the per-connect
    attribute assignments, so disconnect() -> _abort_operators() would read an
    unset self.query_operators. The consumer initializes those attributes in
    __init__ so this teardown path is safe.
    """
    communicator = await _connect(AnonymousUser())
    await communicator.connect()
    # Must complete cleanly (no AttributeError) even though connect() rejected.
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_accepts_authenticated_user():
    user, _, _ = await database_sync_to_async(_build_user_with_access)()
    communicator = await _connect(user)
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_receive_without_permission_returns_access_denied():
    """An authenticated user lacking `add_selectivetransferjob` is allowed to
    connect (auth only) but gets an access-denied error on any command."""
    user = await database_sync_to_async(UserFactory.create)(is_active=True)
    communicator = await _connect(user)
    connected, _ = await communicator.connect()
    assert connected is True

    await communicator.send_json_to({"action": "query"})
    response = await communicator.receive_from(timeout=5)
    assert "Access denied" in response
    assert "don&#x27;t have the proper permission" in response or "permission" in response
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_invalid_action_is_rejected():
    user, _, _ = await database_sync_to_async(_build_user_with_access)()
    communicator = await _connect(user)
    await communicator.connect()

    await communicator.send_json_to({"action": "frobnicate"})
    response = await communicator.receive_from(timeout=5)
    assert "Invalid action to process: frobnicate" in response
    await communicator.disconnect()


# ---------------------------------------------------------------------------
# Query path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_query_dispatches_to_operator_and_streams_results(monkeypatch):
    """A query action must construct a DicomOperator for the source server,
    call find_studies, and stream back the rendered results containing the
    queried study's PatientID."""
    user, source, destination = await database_sync_to_async(_build_user_with_access)()

    captured: dict = {}

    def fake_operator_factory(server):
        captured["server"] = server
        op = MagicMock()
        op.find_studies.return_value = iter(
            [_make_result_study("PAT-QUERY-123", "1.2.3.4.5")]
        )
        op.abort.return_value = None
        return op

    monkeypatch.setattr(consumers_module, "DicomOperator", fake_operator_factory)

    communicator = await _connect(user)
    await communicator.connect()

    await communicator.send_json_to(_query_payload(source, destination))

    # First frame is the "in progress" spinner (sent synchronously).
    first = await communicator.receive_from(timeout=5)
    assert "Searching" in first or "spinner-border" in first

    # The results are sent via a debounced (≈1s) callback from a worker thread.
    rest = await _drain(communicator, timeout=6)
    assert "PAT-QUERY-123" in rest

    # The operator was built for the selected source server. (DicomServer shares
    # its pk with its DicomNode parent row via multi-table inheritance.)
    assert captured["server"].pk == source.pk
    await _safe_disconnect(communicator)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_query_with_no_results_reports_no_studies(monkeypatch):
    user, source, destination = await database_sync_to_async(_build_user_with_access)()

    def fake_operator_factory(server):
        op = MagicMock()
        op.find_studies.return_value = iter([])  # no studies
        op.abort.return_value = None
        return op

    monkeypatch.setattr(consumers_module, "DicomOperator", fake_operator_factory)

    communicator = await _connect(user)
    await communicator.connect()
    await communicator.send_json_to(_query_payload(source, destination))

    await communicator.receive_from(timeout=5)  # spinner
    rest = await _drain(communicator, timeout=6)
    assert "No studies found" in rest
    await _safe_disconnect(communicator)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_query_with_invalid_form_returns_form_errors(monkeypatch):
    """A query referencing a source the user cannot access fails form
    validation and returns a re-rendered form with an error message (no
    DicomOperator is constructed)."""
    user, _source, destination = await database_sync_to_async(_build_user_with_access)()
    # A foreign source the user's group has no access to.
    foreign_source = await database_sync_to_async(DicomServerFactory.create)()

    built: list = []

    def fake_operator_factory(server):
        built.append(server)
        return MagicMock()

    monkeypatch.setattr(consumers_module, "DicomOperator", fake_operator_factory)

    communicator = await _connect(user)
    await communicator.connect()
    await communicator.send_json_to(_query_payload(foreign_source, destination))

    response = await _drain(communicator, timeout=5)
    assert "Please correct the form errors and search again." in response
    # No operator should have been constructed for an invalid form.
    assert built == []
    await _safe_disconnect(communicator)


# ---------------------------------------------------------------------------
# Transfer path  (incl. the "max 10 studies" guard)
# ---------------------------------------------------------------------------


def _transfer_payload(
    source: DicomServer,
    destination: DicomServer,
    selected_studies: list[str],
) -> dict:
    payload = _query_payload(source, destination)
    payload["action"] = "transfer"
    payload["selected_studies"] = selected_studies
    return payload


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transfer_creates_job_and_enqueues_tasks():
    """A valid transfer creates a SelectiveTransferJob with one task per
    selected study and enqueues it (queued_job set on the task)."""
    user, source, destination = await database_sync_to_async(_build_user_with_access)()

    communicator = await _connect(user)
    await communicator.connect()

    selected = ["PAT1\\1.2.3.4.5", "PAT2\\1.2.3.4.6"]
    await communicator.send_json_to(_transfer_payload(source, destination, selected))

    response = await communicator.receive_from(timeout=8)
    assert "Successfully submitted transfer job" in response

    @database_sync_to_async
    def read_db():
        job = SelectiveTransferJob.objects.get(owner=user)
        tasks = list(SelectiveTransferTask.objects.filter(job=job).order_by("patient_id"))
        return job, tasks

    job, tasks = await read_db()
    assert job.status == SelectiveTransferJob.Status.PENDING
    assert len(tasks) == 2
    assert {t.patient_id for t in tasks} == {"PAT1", "PAT2"}
    assert {t.study_uid for t in tasks} == {"1.2.3.4.5", "1.2.3.4.6"}
    # Enqueued: each task got a Procrastinate queued_job id.
    assert all(t.queued_job_id is not None for t in tasks)
    await _safe_disconnect(communicator)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transfer_single_selected_study_as_string():
    """`selected_studies` may arrive as a single string (one checkbox); it must
    be coerced to a one-element list and produce one task."""
    user, source, destination = await database_sync_to_async(_build_user_with_access)()

    communicator = await _connect(user)
    await communicator.connect()

    payload = _transfer_payload(source, destination, [])
    payload["selected_studies"] = "PATX\\9.9.9.9"  # single string, not a list
    await communicator.send_json_to(payload)

    response = await communicator.receive_from(timeout=8)
    assert "Successfully submitted transfer job" in response

    @database_sync_to_async
    def count_tasks():
        job = SelectiveTransferJob.objects.get(owner=user)
        return list(SelectiveTransferTask.objects.filter(job=job))

    tasks = await count_tasks()
    assert len(tasks) == 1
    assert tasks[0].patient_id == "PATX"
    assert tasks[0].study_uid == "9.9.9.9"
    await _safe_disconnect(communicator)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transfer_over_limit_rejected_for_non_staff():
    """A non-staff user transferring more than 10 studies is rejected with the
    guard message and NO job is created."""
    user, source, destination = await database_sync_to_async(_build_user_with_access)(
        is_staff=False
    )
    assert not user.is_staff

    communicator = await _connect(user)
    await communicator.connect()

    selected = [f"PAT{i}\\1.2.3.{i}" for i in range(11)]  # 11 > 10
    await communicator.send_json_to(_transfer_payload(source, destination, selected))

    response = await communicator.receive_from(timeout=8)
    assert "Maximum 10 studies per selective transfer are allowed." in response
    assert "Successfully submitted" not in response

    @database_sync_to_async
    def job_count():
        return SelectiveTransferJob.objects.filter(owner=user).count()

    # The guard runs before form.save(), so no job (and no task) is created.
    assert await job_count() == 0
    await _safe_disconnect(communicator)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transfer_over_limit_allowed_for_staff():
    """A staff user may transfer more than 10 studies (guard does not apply)."""
    user, source, destination = await database_sync_to_async(_build_user_with_access)(
        is_staff=True
    )

    communicator = await _connect(user)
    await communicator.connect()

    selected = [f"PAT{i}\\1.2.3.{i}" for i in range(11)]
    await communicator.send_json_to(_transfer_payload(source, destination, selected))

    response = await communicator.receive_from(timeout=10)
    assert "Successfully submitted transfer job" in response

    @database_sync_to_async
    def task_count():
        job = SelectiveTransferJob.objects.get(owner=user)
        return SelectiveTransferTask.objects.filter(job=job).count()

    assert await task_count() == 11
    await _safe_disconnect(communicator)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_transfer_with_no_selected_studies_does_nothing():
    """If no studies are selected, `make_transfer` returns without sending a
    response or creating a job (the early `is not None` guard means an empty
    payload key is required to reach the ValueError branch)."""
    user, source, destination = await database_sync_to_async(_build_user_with_access)()

    communicator = await _connect(user)
    await communicator.connect()

    # selected_studies key omitted entirely -> make_transfer short-circuits.
    payload = _query_payload(source, destination)
    payload["action"] = "transfer"
    await communicator.send_json_to(payload)

    # Nothing should come back.
    with pytest.raises(Exception):
        await communicator.receive_from(timeout=2)

    @database_sync_to_async
    def job_count():
        return SelectiveTransferJob.objects.filter(owner=user).count()

    assert await job_count() == 0
    await _safe_disconnect(communicator)


# ---------------------------------------------------------------------------
# Direct unit tests of the guard (no WebSocket layer)
# ---------------------------------------------------------------------------


def _valid_transfer_form(user, source, destination):
    from adit.selective_transfer.forms import SelectiveTransferJobForm

    data = _query_payload(source, destination)
    data["action"] = "transfer"
    return SelectiveTransferJobForm(
        data,
        user=user,
        action="transfer",
        advanced_options_collapsed=False,
    )


@pytest.mark.django_db
def test_transfer_selected_studies_guard_raises_value_error():
    """Unit-level: transfer_selected_studies enforces the 10-study cap for
    non-staff via ValueError. The cap is checked BEFORE form.save(), so no job
    row is persisted when the guard trips (no orphaned job)."""
    user, source, destination = _build_user_with_access(is_staff=False)

    consumer = SelectiveTransferConsumer()
    consumer.user = user

    form = _valid_transfer_form(user, source, destination)
    assert form.is_valid(), form.errors

    before = SelectiveTransferJob.objects.count()
    with pytest.raises(ValueError, match="Maximum 10 studies"):
        consumer.transfer_selected_studies(
            user, form, [f"P{i}\\1.2.{i}" for i in range(11)]
        )
    # Guard precedes form.save(): nothing was persisted.
    assert SelectiveTransferJob.objects.count() == before


@pytest.mark.django_db
def test_transfer_selected_studies_empty_raises_value_error():
    """An empty selection raises the dedicated 'at least one study' ValueError
    (also before any save)."""
    user, source, destination = _build_user_with_access(is_staff=False)
    consumer = SelectiveTransferConsumer()
    consumer.user = user
    form = _valid_transfer_form(user, source, destination)
    assert form.is_valid(), form.errors

    before = SelectiveTransferJob.objects.count()
    with pytest.raises(ValueError, match="At least one study"):
        consumer.transfer_selected_studies(user, form, [])
    assert SelectiveTransferJob.objects.count() == before


@pytest.mark.django_db
def test_transfer_selected_studies_creates_job_and_tasks_unit():
    """Unit-level happy path: a valid selection persists the job (PENDING) and
    one task per study, and enqueues them."""
    user, source, destination = _build_user_with_access(is_staff=False)
    consumer = SelectiveTransferConsumer()
    consumer.user = user
    form = _valid_transfer_form(user, source, destination)
    assert form.is_valid(), form.errors

    job = consumer.transfer_selected_studies(
        user, form, ["AAA\\1.1", "BBB\\2.2", "CCC\\3.3"]
    )

    assert job.owner == user
    assert job.status == SelectiveTransferJob.Status.PENDING
    tasks = list(SelectiveTransferTask.objects.filter(job=job))
    assert len(tasks) == 3
    assert {t.patient_id for t in tasks} == {"AAA", "BBB", "CCC"}
    assert all(t.queued_job_id is not None for t in tasks)
