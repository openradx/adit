import asyncio
import contextlib
import errno
import json
import logging
import socket
import struct
import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import sleep

import pytest
import stamina
from django.conf import settings
from pydicom import Dataset
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,  # type: ignore
    StudyRootQueryRetrieveInformationModelFind,  # type: ignore
)
from pytest_django.fixtures import Settings
from pytest_mock import MockerFixture

from adit.core.errors import DicomError, IncompleteFetchError, RetriableDicomError
from adit.core.factories import DicomWebServerFactory
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset
from adit.core.utils.file_transmit import (
    SUBSCRIBED_ACK,
    FileTransmitServer,
    FileTransmitSession,
)
from adit.core.utils.testing_helpers import (
    DicomTestHelper,
    create_association_mock,
    create_dicom_operator,
)

# SOPInstanceUIDs of images the re-fetch tests expect besides the sample image
IMAGE_B = "1.2.3.4.5.901"
IMAGE_C = "1.2.3.4.5.902"


def _make_result(**kwargs) -> ResultDataset:
    ds = Dataset()
    for key, value in kwargs.items():
        setattr(ds, key, value)
    return ResultDataset(ds)


def create_dicomweb_operator() -> DicomOperator:
    """A DicomOperator whose server only supports DICOMweb (QIDO/WADO/STOW)."""
    server = DicomWebServerFactory.create()
    return DicomOperator(server)


@pytest.mark.django_db
def test_find_patients(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientName": "Foo^Bar", "PatientID": "1001"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(dicom_operator.find_patients(QueryDataset.create(PatientName="Foo^Bar")))

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert (
        association_mock.send_c_find.call_args.args[1]
        == PatientRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_find_studies_with_patient_root(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientID": "12345"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(dicom_operator.find_studies(QueryDataset.create(PatientID="12345")))

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert (
        association_mock.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_find_studies_with_study_root(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientName": "Foo^Bar"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(dicom_operator.find_studies(QueryDataset.create(PatientName="Foo^Bar")))

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientName == responses[0]["PatientName"]
    assert (
        association_mock.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_find_series(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    responses = [{"PatientID": "12345", "StudyInstanceUID": "1.123"}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )
    dicom_operator = create_dicom_operator()

    # Act
    patients = list(
        dicom_operator.find_series(QueryDataset.create(PatientID="12345", StudyInstanceUID="1.123"))
    )

    # Assert
    association_mock.send_c_find.assert_called_once()
    assert isinstance(association_mock.send_c_find.call_args.args[0], Dataset)
    assert patients[0].PatientID == responses[0]["PatientID"]
    assert (
        association_mock.send_c_find.call_args.args[1] == StudyRootQueryRetrieveInformationModelFind
    )


@pytest.mark.django_db
def test_download_series_with_c_get(mocker: MockerFixture):
    # Arrange
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    association_mock.send_c_get.return_value = DicomTestHelper.create_successful_c_get_response()
    path = Path(settings.BASE_PATH) / "samples" / "dicoms"
    ds = read_dataset(next(path.rglob("*.dcm")))
    received_ds = []
    dicom_operator = create_dicom_operator()

    # Act
    dicom_operator.fetch_series(
        ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: received_ds.append(ds)
    )

    # Assert
    association_mock.send_c_get.assert_called_once()

    # TODO: This test could be improved, unfortunately the callback of  fetch_series will never get
    # called when we just mock send_c_get. And so we can't assert anything on received_ds.


@pytest.mark.django_db
def test_download_series_with_c_move(settings: Settings, mocker: MockerFixture):
    # Arrange
    settings.FILE_TRANSMIT_HOST = "127.0.0.1"
    settings.FILE_TRANSMIT_PORT = 17999
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    association_mock.send_c_move.return_value = DicomTestHelper.create_successful_c_move_response()
    dicom_operator = create_dicom_operator()
    dicom_operator.server.study_root_get_support = False
    dicom_operator.server.patient_root_get_support = False
    path = Path(settings.BASE_PATH) / "samples" / "dicoms"
    file_path = next(path.rglob("*.dcm"))
    ds = read_dataset(file_path)
    responses = [{"SOPInstanceUID": ds.SOPInstanceUID}]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        responses
    )

    subscribed_topic = ""

    def start_transmit_server():
        transmit_server = FileTransmitServer("127.0.0.1", 17999, write_timeout=30)

        async def on_subscribe(topic: str):
            nonlocal subscribed_topic
            subscribed_topic = topic
            await transmit_server.publish_file(
                topic, file_path, {"SOPInstanceUID": ds.SOPInstanceUID}
            )

        transmit_server.set_subscribe_handler(on_subscribe)
        asyncio.run(transmit_server.start(), debug=True)

    threading.Thread(target=start_transmit_server, daemon=True).start()

    # Make sure transmit server is started
    sleep(0.5)

    received_ds = []

    # Act
    dicom_operator.fetch_series(
        ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: received_ds.append(ds)
    )

    # Assert
    assert subscribed_topic == ds.StudyInstanceUID
    association_mock.send_c_move.assert_called_once()
    assert received_ds[0] == ds


def _frame_header(path: Path, metadata: dict[str, str]) -> bytes:
    """The frame header publish_file builds, for queueing a file to one session directly."""
    return struct.pack("!I", path.stat().st_size) + (json.dumps(metadata) + "\n").encode()


def _start_transmit_server(
    port: int,
    answer_sync: bool = True,
    before_sync: list[threading.Thread] | None = None,
    on_sync: Callable[[FileTransmitSession, str], Awaitable[bool]] | None = None,
) -> tuple[FileTransmitServer, asyncio.AbstractEventLoop]:
    """Run a file transmit server in its own thread like the receiver container does.

    Like the receiver, it answers a sync request only after the publishes the test scheduled
    before it (`before_sync`, e.g. the receiver's backlog). `on_sync` runs on the server's loop
    before the answer (publish there with `await server.publish_file(...)`) and returns
    whether to answer.
    """
    server = FileTransmitServer("127.0.0.1", port, write_timeout=30)

    async def sync_handler(session: FileTransmitSession, token: str):
        for publish in list(before_sync or []):
            if publish.ident is not None:
                await asyncio.to_thread(publish.join)
        if on_sync and not await on_sync(session, token):
            return
        if answer_sync:
            session.queue_synced(token)

    server.set_sync_request_handler(sync_handler)
    loops: list[asyncio.AbstractEventLoop] = []
    started = threading.Event()

    async def serve():
        loops.append(asyncio.get_running_loop())
        started.set()
        await server.start()

    threading.Thread(target=asyncio.run, args=(serve(),), daemon=True).start()
    started.wait()
    sleep(0.5)  # Make sure transmit server is listening
    return server, loops[0]


def _setup_c_move_operator(settings: Settings, mocker: MockerFixture, port: int):
    settings.FILE_TRANSMIT_HOST = "127.0.0.1"
    settings.FILE_TRANSMIT_PORT = port
    settings.C_MOVE_DOWNLOAD_TIMEOUT = 1
    settings.C_MOVE_SYNC_TIMEOUT = 10
    settings.C_MOVE_REFETCH_ATTEMPTS = 2
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = 50
    settings.C_MOVE_FAIL_ON_INCOMPLETE = True
    associate_mock = mocker.patch("adit.core.utils.dimse_connector.AE.associate")
    association_mock = create_association_mock()
    associate_mock.return_value = association_mock
    association_mock.send_c_move.return_value = DicomTestHelper.create_successful_c_move_response()
    dicom_operator = create_dicom_operator()
    dicom_operator.server.study_root_get_support = False
    dicom_operator.server.patient_root_get_support = False
    path = Path(settings.BASE_PATH) / "samples" / "dicoms"
    file_path = next(path.rglob("*.dcm"))
    ds = read_dataset(file_path)
    return dicom_operator, association_mock, file_path, ds


@pytest.mark.django_db
def test_c_move_images_sent_right_away_reach_the_worker(settings: Settings, mocker: MockerFixture):
    # Arrange
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17998
    )
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}]
    )
    transmit_server, loop = _start_transmit_server(17998)

    def send_c_move(*args, **kwargs):
        # The PACS starts sending images as soon as it got the C-MOVE request
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": ds.SOPInstanceUID}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move
    received_ds = []

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, received_ds.append
        )
    finally:
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Assert
    assert received_ds == [ds]


@pytest.mark.django_db
def test_c_move_is_not_sent_when_receiver_is_unreachable(settings: Settings, mocker: MockerFixture):
    # Arrange: nothing listens on the file transmit port
    dicom_operator, association_mock, _, ds = _setup_c_move_operator(settings, mocker, 17997)
    settings.C_MOVE_SUBSCRIBE_TIMEOUT = 2
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}]
    )

    # Act / Assert
    with pytest.raises(RetriableDicomError, match="receiver"):
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )
    association_mock.send_c_move.assert_not_called()


@pytest.mark.django_db
def test_c_move_fails_when_receiver_connection_drops(settings: Settings, mocker: MockerFixture):
    # Arrange: two images expected, the receiver sends one and then drops the connection
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17996
    )
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}, {"SOPInstanceUID": "1.2.3.4.5.999"}]
    )
    data = file_path.read_bytes()
    metadata = (json.dumps({"SOPInstanceUID": ds.SOPInstanceUID}) + "\n").encode()
    listener = socket.create_server(("127.0.0.1", 17996))

    def serve_one_file_then_drop():
        conn, _ = listener.accept()
        with conn:
            conn.recv(1024)  # topic
            conn.sendall(SUBSCRIBED_ACK + struct.pack("!I", len(data)) + metadata + data)

    threading.Thread(target=serve_one_file_then_drop, daemon=True).start()
    received_ds = []

    # Act / Assert
    try:
        with pytest.raises(RetriableDicomError, match="receiver"):
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, received_ds.append
            )
    finally:
        listener.close()
    assert received_ds == [ds]


@pytest.mark.django_db
def test_c_move_raises_errors_of_the_consumer_itself(settings: Settings, mocker: MockerFixture):
    # Arrange: the consumer thread fails before it could subscribe
    dicom_operator, association_mock, _, ds = _setup_c_move_operator(settings, mocker, 17982)
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}]
    )
    mocker.patch(
        "adit.core.utils.dicom_operator.FileTransmitClient", side_effect=RuntimeError("bug")
    )

    # Act / Assert: the real cause, not a misleading "could not subscribe"
    with pytest.raises(RuntimeError, match="bug"):
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )


@pytest.mark.django_db
def test_c_move_images_arriving_after_a_long_move_are_received(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: the move takes longer than the download timeout and the receiver only
    # delivers the image shortly after the move finished
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17995
    )
    settings.C_MOVE_DOWNLOAD_TIMEOUT = 2
    # Shorter than the move, so the wait for the confirmation must start when the move ended
    settings.C_MOVE_SYNC_TIMEOUT = 2
    settings.C_MOVE_REFETCH_ATTEMPTS = 0
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}]
    )
    pending_publishes: list[threading.Thread] = []
    transmit_server, loop = _start_transmit_server(17995, before_sync=pending_publishes)

    def publish():
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": ds.SOPInstanceUID}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)

    # Still in the receiver's backlog when the move ends
    delayed_publish = threading.Timer(1.2, publish)
    pending_publishes.append(delayed_publish)

    def send_c_move(*args, **kwargs):
        sleep(settings.C_MOVE_DOWNLOAD_TIMEOUT + 0.5)
        delayed_publish.start()
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move
    received_ds = []

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, received_ds.append
        )
    finally:
        delayed_publish.cancel()
        if delayed_publish.ident is not None:
            delayed_publish.join()
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Assert
    assert received_ds == [ds]


@pytest.mark.django_db
@pytest.mark.parametrize("answer_sync", [True, False])
def test_c_move_images_of_other_fetches_do_not_extend_the_wait(
    settings: Settings, mocker: MockerFixture, answer_sync: bool
):
    # Arrange: one of two expected images never arrives, while another fetch of the same
    # study keeps receiving images on the same topic
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17994
    )
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}, {"SOPInstanceUID": "1.2.3.4.5.999"}]
    )
    transmit_server, loop = _start_transmit_server(17994, answer_sync=answer_sync)
    stop_other_fetch = threading.Event()

    def publish(image_uid: str):
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": image_uid}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)

    def other_fetch():
        deadline = time.time() + 8
        while not stop_other_fetch.wait(0.2) and time.time() < deadline:
            # The fetch under test may end its subscription in the middle of a publish
            with contextlib.suppress(Exception):
                publish("9.9.9.9")

    other_fetch_thread = threading.Thread(target=other_fetch, daemon=True)

    def send_c_move(*args, **kwargs):
        publish(ds.SOPInstanceUID)
        other_fetch_thread.start()
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False
    settings.C_MOVE_REFETCH_ATTEMPTS = 0
    settings.C_MOVE_SYNC_TIMEOUT = 1

    # Act
    start = time.time()
    try:
        if answer_sync:
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
        else:
            with pytest.raises(RetriableDicomError, match="did not confirm"):
                dicom_operator.fetch_series(
                    ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
                )
    finally:
        stop_other_fetch.set()
        if other_fetch_thread.ident is not None:
            other_fetch_thread.join()
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Assert: neither the wait for the confirmation nor the one for late images is extended
    timeout = settings.C_MOVE_DOWNLOAD_TIMEOUT if answer_sync else settings.C_MOVE_SYNC_TIMEOUT
    assert time.time() - start < 2 * timeout + 2


@pytest.mark.django_db
def test_c_move_study_fetch_finishes_the_series_query_before_querying_images(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: a PACS mixes up the responses when a second C-FIND is sent on the
    # association while the first one still streams its results
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17987
    )
    streaming_queries: list[str] = []
    nested_queries: list[str] = []

    def send_c_find(query_ds: Dataset, *args, **kwargs):
        level = query_ds.QueryRetrieveLevel
        if streaming_queries:
            nested_queries.append(level)

        def responses():
            streaming_queries.append(level)
            try:
                if level == "SERIES":
                    data = [{"SeriesInstanceUID": ds.SeriesInstanceUID, "Modality": ds.Modality}]
                else:
                    data = [{"SOPInstanceUID": ds.SOPInstanceUID}]
                yield from DicomTestHelper.create_successful_c_find_responses(data)
            finally:
                streaming_queries.remove(level)

        return responses()

    association_mock.send_c_find.side_effect = send_c_find
    transmit_server, loop = _start_transmit_server(17987)

    def send_c_move(*args, **kwargs):
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": ds.SOPInstanceUID}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move
    received_ds = []

    # Act
    try:
        dicom_operator.fetch_study(ds.PatientID, ds.StudyInstanceUID, received_ds.append)
    finally:
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Assert
    assert nested_queries == []
    assert received_ds == [ds]


def _failed_c_move_response():
    status = Dataset()
    status.Status = 0xA702  # Out of resources
    return iter([(status, None)])


def _setup_refetch(
    settings: Settings,
    mocker: MockerFixture,
    port: int,
    deliver: set[str],
    images: dict[str, str | None] | None = None,
    on_sync: Callable[[FileTransmitSession, str], Awaitable[bool]] | None = None,
):
    """The sample image and `images` (by default B and C) are expected, each image maps to
    its series (None for the series of the sample image). The first C-MOVE only delivers
    the sample image, IMAGE-level
    C-MOVEs deliver the requested image if it is in `deliver`, otherwise they fail with a
    failure status ("fail" in `deliver`), lose the association ("lose", or "peer abort" while
    the association still counts as alive) or deliver nothing.
    With "late", image C arrives late while image B (not delivered) is fetched again. With
    "delayed", the requested images are still in the receiver's backlog for longer than the
    grace when their C-MOVE finished. With "after sync", the images in `deliver` arrive half a
    grace after the first sync was answered, as from a PACS that sends after its final C-MOVE
    response. With "slow sync", the first sync is answered only after 1.5 graces without any
    image. `on_sync` is passed to the transmit server."""
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(settings, mocker, port)
    # Most images are missing after the first C-MOVE
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = 100
    image_series = {ds.SOPInstanceUID: ds.SeriesInstanceUID} | {
        image_uid: series_uid or ds.SeriesInstanceUID
        for image_uid, series_uid in (images or {IMAGE_B: None, IMAGE_C: None}).items()
    }

    def send_c_find(query_ds: Dataset, *args, **kwargs):
        if query_ds.QueryRetrieveLevel == "SERIES":
            series_uids = dict.fromkeys(image_series.values())
            data = [{"SeriesInstanceUID": uid, "Modality": ds.Modality} for uid in series_uids]
        else:
            data = [
                {"SOPInstanceUID": image_uid}
                for image_uid, series_uid in image_series.items()
                if series_uid == query_ds.SeriesInstanceUID
            ]
        return DicomTestHelper.create_successful_c_find_responses(data)

    association_mock.send_c_find.side_effect = send_c_find
    refetch_missing_images = mocker.spy(dicom_operator, "_refetch_missing_images")
    requested: list[tuple[str, str, str]] = []
    delayed_publishes: list[threading.Thread] = []
    late_publishes: list[threading.Timer] = []
    syncs = 0

    async def answer_sync(session: FileTransmitSession, token: str) -> bool:
        nonlocal syncs
        syncs += 1
        if "slow sync" in deliver and syncs == 1:
            await asyncio.sleep(1.5 * settings.C_MOVE_DOWNLOAD_TIMEOUT)
        if "after sync" in deliver and syncs == 1:
            for image_uid in deliver & {IMAGE_B, IMAGE_C}:
                late_publish = threading.Timer(
                    0.5 * settings.C_MOVE_DOWNLOAD_TIMEOUT, publish, args=[image_uid]
                )
                late_publishes.append(late_publish)
                late_publish.start()
        return await on_sync(session, token) if on_sync else True

    transmit_server, loop = _start_transmit_server(
        port, before_sync=delayed_publishes, on_sync=answer_sync
    )

    def publish(image_uid: str):
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": image_uid}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)

    def send_c_move(query_ds: Dataset, *args, **kwargs):
        if query_ds.QueryRetrieveLevel != "IMAGE":
            publish(ds.SOPInstanceUID)
            return DicomTestHelper.create_successful_c_move_response()

        image_uid = query_ds.SOPInstanceUID
        requested.append((query_ds.QueryRetrieveLevel, query_ds.SeriesInstanceUID, image_uid))
        if "late" in deliver and image_uid == IMAGE_B:
            publish(IMAGE_C)
            # Let the consumer hand it over
            missing_images = refetch_missing_images.call_args.args[1]
            deadline = time.monotonic() + 5
            while IMAGE_C in missing_images:
                assert time.monotonic() < deadline
                sleep(0.01)
        if image_uid in deliver and "delayed" in deliver:
            delay = 1.5 * settings.C_MOVE_DOWNLOAD_TIMEOUT
            delayed_publishes.append(threading.Timer(delay, publish, args=[image_uid]))
            delayed_publishes[-1].start()
        elif image_uid in deliver:
            publish(image_uid)
        elif "fail" in deliver:
            return _failed_c_move_response()
        elif "lose" in deliver:
            # How pynetdicom reports a timed out or aborted association
            association_mock.is_alive.return_value = False
            return iter([(Dataset(), None)])
        elif "peer abort" in deliver:
            # Its reactor thread only stops a moment after an A-ABORT of the peer
            return iter([(Dataset(), None)])
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move

    def stop():
        for late_publish in late_publishes:
            late_publish.cancel()
        for publish_thread in delayed_publishes + late_publishes:
            if publish_thread.ident is not None:
                publish_thread.join()
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    return dicom_operator, ds, requested, stop


@pytest.mark.django_db
def test_c_move_refetches_missing_images_on_one_association(
    settings: Settings, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    # Arrange
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17993, deliver={IMAGE_B, IMAGE_C}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    open_connection = mocker.spy(dicom_operator.dimse_connector, "open_connection")
    received: list[str] = []

    # Act
    try:
        with caplog.at_level(logging.INFO):
            dicom_operator.fetch_series(
                ds.PatientID,
                ds.StudyInstanceUID,
                ds.SeriesInstanceUID,
                lambda ds: received.append(ds.SOPInstanceUID),
            )
    finally:
        stop()

    # Re-fetched images are expected, not late
    assert not _late_image_entries(caplog)

    # Assert
    assert len(received) == 3
    assert requested == [
        ("IMAGE", ds.SeriesInstanceUID, IMAGE_B),
        ("IMAGE", ds.SeriesInstanceUID, IMAGE_C),
    ]
    # C-FIND, first C-MOVE and one association for both IMAGE-level C-MOVEs
    assert open_connection.call_count == 3
    assert dicom_operator.dimse_connector.auto_close is True
    assert dicom_operator.dimse_connector.assoc is None


@pytest.mark.django_db
def test_c_move_study_refetch_requests_each_image_with_its_own_series(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: image B belongs to the series of the sample image, image C to another one
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings,
        mocker,
        17978,
        deliver={IMAGE_B, IMAGE_C},
        images={IMAGE_B: None, IMAGE_C: "1.2.3.4.5.77"},
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1

    # Act
    try:
        dicom_operator.fetch_study(ds.PatientID, ds.StudyInstanceUID, lambda ds: None)
    finally:
        stop()

    # Assert
    assert requested == [
        ("IMAGE", ds.SeriesInstanceUID, IMAGE_B),
        ("IMAGE", "1.2.3.4.5.77", IMAGE_C),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attempts, refetched",
    [(0, []), (1, [IMAGE_B, IMAGE_C]), (3, [IMAGE_B, IMAGE_C, IMAGE_C, IMAGE_C])],
)
def test_c_move_refetch_rounds_only_request_images_still_missing(
    settings: Settings, mocker: MockerFixture, attempts: int, refetched: list[str]
):
    # Arrange: image B arrives in the first re-fetch round, image C never
    dicom_operator, ds, requested, stop = _setup_refetch(settings, mocker, 17992, deliver={IMAGE_B})
    settings.C_MOVE_REFETCH_ATTEMPTS = attempts
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )
    finally:
        stop()

    # Assert
    assert [image_uid for _, _, image_uid in requested] == refetched


@pytest.mark.django_db
def test_c_move_refetch_round_waits_for_images_arriving_after_its_moves(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: the first round already waited the download timeout, the re-fetched images
    # arrive shortly after their C-MOVEs finished
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17981, deliver={IMAGE_B, IMAGE_C, "delayed"}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    settings.C_MOVE_DOWNLOAD_TIMEOUT = 2
    received: list[str] = []

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID,
            ds.StudyInstanceUID,
            ds.SeriesInstanceUID,
            lambda ds: received.append(ds.SOPInstanceUID),
        )
    finally:
        stop()

    # Assert
    assert len(received) == 3


@pytest.mark.django_db
def test_c_move_refetch_keeps_the_association_of_a_persistent_operator(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: a persistent operator (as mass transfer uses) doesn't close its association
    dicom_operator, ds, _, stop = _setup_refetch(
        settings, mocker, 17980, deliver={IMAGE_B, IMAGE_C}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    dicom_operator.dimse_connector.auto_close = False
    open_connection = mocker.spy(dicom_operator.dimse_connector, "open_connection")

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )
    finally:
        stop()

    # Assert: C-FIND, then one C-MOVE association used for the first move and the re-fetch
    assert open_connection.call_count == 2
    assert dicom_operator.dimse_connector.assoc is not None


@pytest.mark.django_db
def test_c_move_refetch_skips_images_that_arrived_meanwhile(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: image C arrives late while image B is fetched again, B never arrives
    dicom_operator, ds, requested, stop = _setup_refetch(settings, mocker, 17983, deliver={"late"})
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False
    received: list[str] = []

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID,
            ds.StudyInstanceUID,
            ds.SeriesInstanceUID,
            lambda ds: received.append(ds.SOPInstanceUID),
        )
    finally:
        stop()

    # Assert
    assert [image_uid for _, _, image_uid in requested] == [IMAGE_B]
    assert len(received) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("max_missing_percent, refetched", [(70, [IMAGE_B, IMAGE_C]), (60, [])])
def test_c_move_refetch_is_skipped_when_too_many_images_are_missing(
    settings: Settings, mocker: MockerFixture, max_missing_percent: int, refetched: list[str]
):
    # Arrange: two of three images (67 %) are missing after the first C-MOVE
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17984, deliver={IMAGE_B, IMAGE_C}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = max_missing_percent

    # Act
    try:
        with contextlib.suppress(RetriableDicomError):
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        stop()

    # Assert
    assert [image_uid for _, _, image_uid in requested] == refetched


@pytest.mark.django_db
def test_c_move_refetch_cap_allows_exactly_the_configured_percentage(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: one of two images (50 %) is missing after the first C-MOVE
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17977, deliver={IMAGE_B}, images={IMAGE_B: None}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = 50

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )
    finally:
        stop()

    # Assert
    assert [image_uid for _, _, image_uid in requested] == [IMAGE_B]


@pytest.mark.django_db
def test_c_move_fails_as_a_whole_when_too_many_images_are_missing(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: two of three images (67 %) are missing, more than the cap allows to fetch again;
    # the delivery is broken as a whole, so even a configured warning doesn't apply
    dicom_operator, ds, _, stop = _setup_refetch(settings, mocker, 17979, deliver=set())
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = 60

    # Act
    try:
        with pytest.raises(RetriableDicomError, match="2 of 3 images") as error:
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        stop()

    # Assert: retried as a whole, not an incomplete result after the re-fetch
    assert not isinstance(error.value, IncompleteFetchError)


@pytest.mark.django_db
def test_c_move_refetch_continues_after_a_failing_move_without_retrying_it(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: the re-fetch of image B fails, image C arrives
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17991, deliver={IMAGE_C, "fail"}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False
    open_connection = mocker.spy(dicom_operator.dimse_connector, "open_connection")
    received: list[str] = []

    # Act: network retries without their waits
    try:
        with stamina.set_testing(True, attempts=10, cap=True):
            dicom_operator.fetch_series(
                ds.PatientID,
                ds.StudyInstanceUID,
                ds.SeriesInstanceUID,
                lambda ds: received.append(ds.SOPInstanceUID),
            )
    finally:
        stop()

    # Assert: the failing C-MOVE was sent once and the next image still fetched
    assert [image_uid for _, _, image_uid in requested] == [IMAGE_B, IMAGE_C]
    assert len(received) == 2
    # A failure status doesn't end the association: C-FIND, first C-MOVE, re-fetch
    assert open_connection.call_count == 3


@pytest.mark.django_db
@pytest.mark.parametrize("loss", ["lose", "peer abort"])
def test_c_move_refetch_stops_when_the_association_is_lost(
    settings: Settings, mocker: MockerFixture, loss: str
):
    # Arrange: the association is lost while image B is fetched again
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17985, deliver={IMAGE_C, loss}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 2

    # Act / Assert: no further C-MOVEs, the task retry takes over
    try:
        with stamina.set_testing(True, attempts=10, cap=True):
            with pytest.raises(RetriableDicomError, match="association"):
                dicom_operator.fetch_series(
                    ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
                )
    finally:
        stop()

    assert [image_uid for _, _, image_uid in requested] == [IMAGE_B]


@pytest.mark.django_db
def test_c_move_fails_when_images_are_still_missing(settings: Settings, mocker: MockerFixture):
    # Arrange: images B and C never arrive
    dicom_operator, ds, _, stop = _setup_refetch(settings, mocker, 17990, deliver=set())
    settings.C_MOVE_REFETCH_ATTEMPTS = 0

    # Act
    try:
        with pytest.raises(IncompleteFetchError, match="2 of 3 images") as error:
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        stop()

    # Assert
    assert error.value.study_uid == ds.StudyInstanceUID
    assert error.value.missing_image_uids == [IMAGE_B, IMAGE_C]
    assert error.value.image_count == 3


@pytest.mark.django_db
def test_c_move_only_warns_about_missing_images_when_configured(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: images B and C never arrive
    dicom_operator, ds, _, stop = _setup_refetch(settings, mocker, 17989, deliver=set())
    settings.C_MOVE_REFETCH_ATTEMPTS = 0
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )
    finally:
        stop()

    # Assert
    assert [log["title"] for log in dicom_operator.get_logs()] == [
        "Some images could not be fetched"
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("max_missing_percent", [50, 100])
def test_c_move_does_not_refetch_when_no_image_arrived(
    settings: Settings, mocker: MockerFixture, max_missing_percent: int
):
    # Arrange: the C-MOVE succeeds, but the receiver delivers none of the two images; even
    # a cap that allows any share of missing images doesn't re-fetch all of them
    dicom_operator, association_mock, _, ds = _setup_c_move_operator(settings, mocker, 17986)
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = max_missing_percent
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}, {"SOPInstanceUID": IMAGE_B}]
    )
    transmit_server, loop = _start_transmit_server(17986)

    # Act / Assert
    try:
        with pytest.raises(RetriableDicomError, match="Failed to fetch all images"):
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Only the first C-MOVE, no IMAGE-level C-MOVE per image of the study
    assert association_mock.send_c_move.call_count == 1


@pytest.mark.django_db
def test_c_move_fails_when_no_image_arrives_even_if_configured_to_warn(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: the C-MOVE succeeds, but the receiver never delivers anything
    dicom_operator, association_mock, _, ds = _setup_c_move_operator(settings, mocker, 17988)
    settings.C_MOVE_REFETCH_ATTEMPTS = 0
    settings.C_MOVE_FAIL_ON_INCOMPLETE = False
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}]
    )
    transmit_server, loop = _start_transmit_server(17988)

    # Act / Assert
    try:
        with pytest.raises(RetriableDicomError, match="Failed to fetch all images"):
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)


def _late_image_entries(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "arrived after the receiver confirmed" in record.getMessage()
    ]


@pytest.mark.django_db
def test_c_move_waits_for_a_receiver_backlog_without_refetching(
    settings: Settings, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    # Arrange: the second image is still in the receiver's backlog for longer than the grace
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17976
    )
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}, {"SOPInstanceUID": IMAGE_B}]
    )
    backlog: list[threading.Thread] = []
    transmit_server, loop = _start_transmit_server(17976, before_sync=backlog)

    def publish(image_uid: str):
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": image_uid}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)

    def send_c_move(*args, **kwargs):
        publish(ds.SOPInstanceUID)
        backlog.append(threading.Timer(2.5 * settings.C_MOVE_DOWNLOAD_TIMEOUT, publish, [IMAGE_B]))
        backlog[-1].start()
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move
    received: list[str] = []

    # Act
    try:
        with caplog.at_level(logging.INFO):
            dicom_operator.fetch_series(
                ds.PatientID,
                ds.StudyInstanceUID,
                ds.SeriesInstanceUID,
                lambda ds: received.append(ds.SOPInstanceUID),
            )
    finally:
        for publish_thread in backlog:
            publish_thread.join()
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Assert: no IMAGE-level C-MOVE, the image came from the receiver
    assert len(received) == 2
    assert association_mock.send_c_move.call_count == 1
    assert not _late_image_entries(caplog)


@pytest.mark.django_db
def test_c_move_decision_waits_for_the_sync_after_the_grace(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: image B reaches the receiver during the grace, but the receiver only gets to
    # forward it right before it answers the second sync
    syncs = 0

    async def on_sync(session: FileTransmitSession, token: str) -> bool:
        nonlocal syncs
        syncs += 1
        if syncs == 2:
            metadata = {"SOPInstanceUID": IMAGE_B}
            session.queue_frame(_frame_header(sample_file, metadata), sample_file)
        return True

    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17975, deliver=set(), images={IMAGE_B: None}, on_sync=on_sync
    )
    sample_file = next((Path(settings.BASE_PATH) / "samples" / "dicoms").rglob("*.dcm"))

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
        )
    finally:
        stop()

    # Assert
    assert requested == []


@pytest.mark.django_db
def test_c_move_tolerates_a_pacs_that_sends_after_its_final_response(
    settings: Settings, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    # Arrange: images B and C arrive half a grace after the receiver confirmed the delivery
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17974, deliver={IMAGE_B, IMAGE_C, "after sync"}
    )
    received: list[str] = []

    # Act
    try:
        with caplog.at_level(logging.INFO):
            dicom_operator.fetch_series(
                ds.PatientID,
                ds.StudyInstanceUID,
                ds.SeriesInstanceUID,
                lambda ds: received.append(ds.SOPInstanceUID),
            )
    finally:
        stop()

    # Assert
    assert len(received) == 3
    assert requested == []
    assert len(_late_image_entries(caplog)) == 1


@pytest.mark.django_db
def test_c_move_grace_starts_when_the_receiver_confirmed(settings: Settings, mocker: MockerFixture):
    # Arrange: the confirmation comes only after more than a grace without any image, then the
    # late images arrive within a grace
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17968, deliver={IMAGE_B, IMAGE_C, "after sync", "slow sync"}
    )
    received: list[str] = []

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID,
            ds.StudyInstanceUID,
            ds.SeriesInstanceUID,
            lambda ds: received.append(ds.SOPInstanceUID),
        )
    finally:
        stop()

    # Assert
    assert len(received) == 3
    assert requested == []


@pytest.mark.django_db
def test_c_move_waits_for_a_slow_callback_instead_of_refetching(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: image B arrives after the confirmation, and handing it over takes longer than
    # the grace
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17967, deliver={IMAGE_B, "after sync"}, images={IMAGE_B: None}
    )
    handed_over: list[str] = []

    def slow_callback(ds: Dataset):
        if handed_over:
            sleep(2 * settings.C_MOVE_DOWNLOAD_TIMEOUT)
        handed_over.append(ds.SOPInstanceUID)

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, slow_callback
        )
    finally:
        stop()

    # Assert
    assert len(handed_over) == 2
    assert requested == []


@pytest.mark.django_db
@pytest.mark.timeout(15)
def test_c_move_ends_when_late_images_stop_coming(settings: Settings, mocker: MockerFixture):
    # Arrange: image B arrives after the confirmation, image C never
    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17973, deliver={IMAGE_B, "after sync"}
    )
    settings.C_MOVE_REFETCH_ATTEMPTS = 1

    # Act
    start = time.monotonic()
    try:
        with pytest.raises(IncompleteFetchError) as error:
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        stop()

    # Assert
    assert error.value.missing_image_uids == [IMAGE_C]
    assert [image_uid for _, _, image_uid in requested] == [IMAGE_C]
    assert time.monotonic() - start < 4 * settings.C_MOVE_DOWNLOAD_TIMEOUT + 2.5


@pytest.mark.django_db
def test_c_move_fails_when_the_receiver_does_not_confirm(settings: Settings, mocker: MockerFixture):
    # Arrange: the receiver never answers the sync request
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17972
    )
    settings.C_MOVE_SYNC_TIMEOUT = 1
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": ds.SOPInstanceUID}, {"SOPInstanceUID": IMAGE_B}]
    )
    transmit_server, loop = _start_transmit_server(17972, answer_sync=False)

    def send_c_move(*args, **kwargs):
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": ds.SOPInstanceUID}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move

    # Act / Assert
    try:
        with pytest.raises(RetriableDicomError, match="did not confirm"):
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    assert association_mock.send_c_move.call_count == 1


@pytest.mark.django_db
def test_c_move_keeps_waiting_for_the_sync_while_images_arrive(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: four more images trickle in from the receiver's backlog, 0.6 s apart, which
    # takes longer than the sync timeout as a whole
    dicom_operator, association_mock, file_path, ds = _setup_c_move_operator(
        settings, mocker, 17971
    )
    settings.C_MOVE_SYNC_TIMEOUT = 2
    trickled = [f"1.2.3.4.5.91{i}" for i in range(4)]
    association_mock.send_c_find.return_value = DicomTestHelper.create_successful_c_find_responses(
        [{"SOPInstanceUID": uid} for uid in [ds.SOPInstanceUID, *trickled]]
    )
    backlog: list[threading.Thread] = []
    transmit_server, loop = _start_transmit_server(17971, before_sync=backlog)

    def publish(image_uid: str):
        publish = transmit_server.publish_file(
            ds.StudyInstanceUID, file_path, {"SOPInstanceUID": image_uid}
        )
        asyncio.run_coroutine_threadsafe(publish, loop).result(timeout=5)

    def trickle():
        for image_uid in trickled:
            sleep(0.6)
            publish(image_uid)

    def send_c_move(*args, **kwargs):
        publish(ds.SOPInstanceUID)
        backlog.append(threading.Thread(target=trickle))
        backlog[-1].start()
        return DicomTestHelper.create_successful_c_move_response()

    association_mock.send_c_move.side_effect = send_c_move
    received: list[str] = []

    # Act
    try:
        dicom_operator.fetch_series(
            ds.PatientID,
            ds.StudyInstanceUID,
            ds.SeriesInstanceUID,
            lambda ds: received.append(ds.SOPInstanceUID),
        )
    finally:
        for publish_thread in backlog:
            publish_thread.join()
        asyncio.run_coroutine_threadsafe(transmit_server.stop(), loop).result(timeout=5)

    # Assert
    assert len(received) == 5
    assert association_mock.send_c_move.call_count == 1


@pytest.mark.django_db
def test_c_move_succeeds_when_the_last_image_arrives_while_a_sync_is_pending(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: the receiver forwards the last missing image instead of answering the sync
    async def on_sync(session: FileTransmitSession, token: str) -> bool:
        for image_uid in [IMAGE_B, IMAGE_C]:
            metadata = {"SOPInstanceUID": image_uid}
            session.queue_frame(_frame_header(sample_file, metadata), sample_file)
        return False

    dicom_operator, ds, requested, stop = _setup_refetch(
        settings, mocker, 17970, deliver=set(), on_sync=on_sync
    )
    sample_file = next((Path(settings.BASE_PATH) / "samples" / "dicoms").rglob("*.dcm"))
    received: list[str] = []

    # Act
    start = time.monotonic()
    try:
        dicom_operator.fetch_series(
            ds.PatientID,
            ds.StudyInstanceUID,
            ds.SeriesInstanceUID,
            lambda ds: received.append(ds.SOPInstanceUID),
        )
    finally:
        stop()

    # Assert: done without the confirmation, long before the sync timeout
    assert len(received) == 3
    assert requested == []
    assert time.monotonic() - start < settings.C_MOVE_SYNC_TIMEOUT / 2


@pytest.mark.django_db
def test_c_move_reports_a_lost_connection_while_syncing_as_retriable(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: the receiver's connection to the worker breaks when the sync arrives
    async def on_sync(session: FileTransmitSession, token: str) -> bool:
        session._writer.transport.abort()
        return False

    dicom_operator, ds, _, stop = _setup_refetch(
        settings, mocker, 17969, deliver=set(), on_sync=on_sync
    )

    # Act / Assert
    try:
        with pytest.raises(RetriableDicomError, match="Connection to the DICOM receiver failed"):
            dicom_operator.fetch_series(
                ds.PatientID, ds.StudyInstanceUID, ds.SeriesInstanceUID, lambda ds: None
            )
    finally:
        stop()


# ---------------------------------------------------------------------------
# DICOMweb (QIDO) find paths and programmatic filtering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_patients_with_qido_and_dedup(mocker: MockerFixture):
    """DICOMweb server: study-level QIDO results are deduplicated to unique patients."""
    operator = create_dicomweb_operator()
    results = [
        _make_result(PatientID="1001", PatientName="Foo^Bar", PatientBirthDate="20000101"),
        _make_result(PatientID="1001", PatientName="Foo^Bar", PatientBirthDate="20000101"),
        _make_result(PatientID="1002", PatientName="Baz^Qux", PatientBirthDate="19900202"),
    ]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    patients = list(operator.find_patients(QueryDataset.create(PatientName="*")))

    qido_mock.assert_called_once()
    # Query retrieve level is forced to STUDY for QIDO patient emulation
    assert qido_mock.call_args.args[0].QueryRetrieveLevel == "STUDY"
    assert [p.PatientID for p in patients] == ["1001", "1002"]


@pytest.mark.django_db
def test_find_patients_filters_by_birth_date_name_and_sex(mocker: MockerFixture):
    operator = create_dicom_operator()
    results = [
        _make_result(
            PatientID="1", PatientName="Foo^Bar", PatientBirthDate="20000101", PatientSex="M"
        ),  # noqa: E501
        _make_result(
            PatientID="2", PatientName="Foo^Baz", PatientBirthDate="20000101", PatientSex="M"
        ),  # noqa: E501
        _make_result(
            PatientID="3", PatientName="Foo^Bar", PatientBirthDate="19991231", PatientSex="M"
        ),  # noqa: E501
        _make_result(
            PatientID="4", PatientName="Foo^Bar", PatientBirthDate="20000101", PatientSex="F"
        ),  # noqa: E501
    ]
    mocker.patch.object(operator.dimse_connector, "send_c_find", return_value=iter(results))

    # PatientSex is not a `create()` kwarg, so build the query dataset directly.
    query_ds = Dataset()
    query_ds.PatientName = "Foo^Bar"
    query_ds.PatientBirthDate = "20000101"
    query_ds.PatientSex = "M"
    query = QueryDataset(query_ds)
    patients = list(operator.find_patients(query))

    # Only patient 1 matches all three filters
    assert [p.PatientID for p in patients] == ["1"]


@pytest.mark.django_db
def test_find_patients_raises_when_no_method_supported(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.patient_root_find_support = False
    operator.server.study_root_find_support = False
    operator.server.dicomweb_qido_support = False

    with pytest.raises(DicomError, match="No supported method to find patients"):
        list(operator.find_patients(QueryDataset.create(PatientID="1")))


@pytest.mark.django_db
def test_find_studies_with_qido_filters_description_and_modalities(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    results = [
        _make_result(
            PatientID="1",
            StudyInstanceUID="1.1",
            StudyDescription="Brain CT",
            ModalitiesInStudy=["CT"],
        ),
        _make_result(
            PatientID="1",
            StudyInstanceUID="1.2",
            StudyDescription="Chest XR",
            ModalitiesInStudy=["XR"],
        ),
    ]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    query = QueryDataset.create(StudyDescription="Brain*", ModalitiesInStudy="CT")
    studies = list(operator.find_studies(query))

    qido_mock.assert_called_once()
    assert [s.StudyInstanceUID for s in studies] == ["1.1"]


@pytest.mark.django_db
def test_find_studies_raises_when_no_method_supported(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.patient_root_find_support = False
    operator.server.study_root_find_support = False
    operator.server.dicomweb_qido_support = False

    with pytest.raises(DicomError, match="No supported method to find studies"):
        list(operator.find_studies(QueryDataset.create(PatientID="1")))


@pytest.mark.django_db
# "1.*" is an intentionally invalid (wildcard) StudyInstanceUID used to assert it
# is rejected; pydicom's VR validation warns on it, which is expected here.
@pytest.mark.filterwarnings("ignore:Invalid value for VR UI:UserWarning")
def test_find_series_requires_valid_study_uid():
    operator = create_dicom_operator()

    with pytest.raises(DicomError, match="valid StudyInstanceUID is required"):
        list(operator.find_series(QueryDataset.create(PatientID="1")))

    with pytest.raises(DicomError, match="valid StudyInstanceUID is required"):
        list(operator.find_series(QueryDataset.create(PatientID="1", StudyInstanceUID="1.*")))


@pytest.mark.django_db
def test_find_series_patient_root_requires_patient_id(mocker: MockerFixture):
    """With only patient root support, querying series without a PatientID raises."""
    operator = create_dicom_operator()
    operator.server.study_root_find_support = False
    operator.server.patient_root_find_support = True

    with pytest.raises(DicomError, match="PatientID is required for querying series"):
        list(operator.find_series(QueryDataset.create(StudyInstanceUID="1.123")))


@pytest.mark.django_db
def test_find_series_filters_number_modality_and_description(mocker: MockerFixture):
    operator = create_dicom_operator()
    results = [
        _make_result(
            SeriesInstanceUID="1.2.3.1", SeriesNumber=1, Modality="CT", SeriesDescription="Axial"
        ),
        _make_result(
            SeriesInstanceUID="1.2.3.2", SeriesNumber=2, Modality="CT", SeriesDescription="Axial"
        ),
        _make_result(
            SeriesInstanceUID="1.2.3.3", SeriesNumber=1, Modality="MR", SeriesDescription="Axial"
        ),
        _make_result(
            SeriesInstanceUID="1.2.3.4", SeriesNumber=1, Modality="CT", SeriesDescription="Sagittal"
        ),
    ]
    mocker.patch.object(operator.dimse_connector, "send_c_find", return_value=iter(results))

    query = QueryDataset.create(
        PatientID="1",
        StudyInstanceUID="1.123",
        SeriesNumber=1,
        Modality="CT",
        SeriesDescription="Axial",
    )
    series = list(operator.find_series(query))

    assert [s.SeriesInstanceUID for s in series] == ["1.2.3.1"]


@pytest.mark.django_db
def test_find_series_uses_qido_when_only_dicomweb(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    results = [_make_result(SeriesInstanceUID="1.2.3.1", PatientID="1", StudyInstanceUID="1.123")]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    series = list(
        operator.find_series(QueryDataset.create(PatientID="1", StudyInstanceUID="1.123"))
    )

    qido_mock.assert_called_once()
    assert series[0].SeriesInstanceUID == "1.2.3.1"


@pytest.mark.django_db
def test_find_images_requires_valid_study_and_series_uid():
    operator = create_dicom_operator()

    with pytest.raises(DicomError, match="valid StudyInstanceUID is required"):
        list(operator.find_images(QueryDataset.create(PatientID="1", SeriesInstanceUID="1.2.3.1")))

    with pytest.raises(DicomError, match="valid SeriesInstanceUID is required"):
        list(operator.find_images(QueryDataset.create(PatientID="1", StudyInstanceUID="1.123")))


@pytest.mark.django_db
def test_find_images_patient_root_requires_patient_id(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.study_root_find_support = False
    operator.server.patient_root_find_support = True

    with pytest.raises(DicomError, match="PatientID is required for querying images"):
        list(
            operator.find_images(
                QueryDataset.create(StudyInstanceUID="1.123", SeriesInstanceUID="1.2.3.1")
            )
        )


@pytest.mark.django_db
def test_find_images_with_c_find(mocker: MockerFixture):
    operator = create_dicom_operator()
    results = [_make_result(SOPInstanceUID="1.2.4.1"), _make_result(SOPInstanceUID="1.2.4.2")]
    find_mock = mocker.patch.object(
        operator.dimse_connector, "send_c_find", return_value=iter(results)
    )

    images = list(
        operator.find_images(
            QueryDataset.create(
                PatientID="1", StudyInstanceUID="1.123", SeriesInstanceUID="1.2.3.1"
            )
        )
    )

    find_mock.assert_called_once()
    assert [i.SOPInstanceUID for i in images] == ["1.2.4.1", "1.2.4.2"]


@pytest.mark.django_db
def test_find_images_with_qido(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    results = [_make_result(SOPInstanceUID="1.2.4.1")]
    qido_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_qido_rs", return_value=iter(results)
    )

    images = list(
        operator.find_images(
            QueryDataset.create(
                PatientID="1", StudyInstanceUID="1.123", SeriesInstanceUID="1.2.3.1"
            )
        )
    )

    qido_mock.assert_called_once()
    assert images[0].SOPInstanceUID == "1.2.4.1"


@pytest.mark.django_db
def test_find_images_raises_when_no_method_supported(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.patient_root_find_support = False
    operator.server.study_root_find_support = False
    operator.server.dicomweb_qido_support = False

    with pytest.raises(DicomError, match="No supported method to find images"):
        list(
            operator.find_images(
                QueryDataset.create(
                    PatientID="1", StudyInstanceUID="1.123", SeriesInstanceUID="1.2.3.1"
                )
            )
        )


# ---------------------------------------------------------------------------
# fetch_* dispatch (WADO preferred) and "no supported method" errors
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_study_prefers_wado(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    image = Dataset()
    image.SOPInstanceUID = "1.2.4.1"
    wado_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_wado_rs", return_value=iter([image])
    )

    received: list[Dataset] = []
    operator.fetch_study("1", "1.123", received.append)

    wado_mock.assert_called_once()
    assert received[0].SOPInstanceUID == "1.2.4.1"


@pytest.mark.django_db
def test_fetch_study_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    for attr in (
        "dicomweb_wado_support",
        "patient_root_get_support",
        "study_root_get_support",
        "patient_root_move_support",
        "study_root_move_support",
    ):
        setattr(operator.server, attr, False)

    with pytest.raises(DicomError, match="No supported method to fetch a study"):
        operator.fetch_study("1", "1.123", lambda ds: None)


@pytest.mark.django_db
def test_fetch_series_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    for attr in (
        "dicomweb_wado_support",
        "patient_root_get_support",
        "study_root_get_support",
        "patient_root_move_support",
        "study_root_move_support",
    ):
        setattr(operator.server, attr, False)

    with pytest.raises(DicomError, match="No supported method to fetch a series"):
        operator.fetch_series("1", "1.123", "1.2.3.1", lambda ds: None)


@pytest.mark.django_db
def test_fetch_image_prefers_wado(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    image = Dataset()
    image.SOPInstanceUID = "1.2.4.1"
    wado_mock = mocker.patch.object(
        operator.dicom_web_connector, "send_wado_rs", return_value=iter([image])
    )

    received: list[Dataset] = []
    operator.fetch_image("1", "1.123", "1.2.3.1", "1.2.4.1", received.append)

    wado_mock.assert_called_once()
    assert received[0].SOPInstanceUID == "1.2.4.1"


@pytest.mark.django_db
def test_fetch_image_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    for attr in (
        "dicomweb_wado_support",
        "patient_root_get_support",
        "study_root_get_support",
        "patient_root_move_support",
        "study_root_move_support",
    ):
        setattr(operator.server, attr, False)

    with pytest.raises(DicomError, match="No supported method to fetch an image"):
        operator.fetch_image("1", "1.123", "1.2.3.1", "1.2.4.1", lambda ds: None)


# ---------------------------------------------------------------------------
# upload_images
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_images_uses_c_store(mocker: MockerFixture):
    operator = create_dicom_operator()
    store_mock = mocker.patch.object(operator.dimse_connector, "send_c_store")
    datasets = [Dataset()]

    operator.upload_images(datasets)

    store_mock.assert_called_once_with(datasets)


@pytest.mark.django_db
def test_upload_images_uses_stow_when_only_dicomweb(mocker: MockerFixture):
    operator = create_dicomweb_operator()
    stow_mock = mocker.patch.object(operator.dicom_web_connector, "send_stow_rs")
    datasets = [Dataset()]

    operator.upload_images(datasets)

    stow_mock.assert_called_once_with(datasets)


@pytest.mark.django_db
def test_upload_images_raises_when_no_method(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.server.store_scp_support = False
    operator.server.dicomweb_stow_support = False

    with pytest.raises(DicomError, match="No supported method to upload images"):
        operator.upload_images([Dataset()])


# ---------------------------------------------------------------------------
# move_study / move_series
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_move_study_sends_c_move(mocker: MockerFixture):
    operator = create_dicom_operator()
    move_mock = mocker.patch.object(operator.dimse_connector, "send_c_move")

    operator.move_study("1", "1.123", "DEST_AE")

    move_mock.assert_called_once()
    query, dest = move_mock.call_args.args
    assert query.QueryRetrieveLevel == "STUDY"
    assert query.StudyInstanceUID == "1.123"
    assert dest == "DEST_AE"


@pytest.mark.django_db
def test_move_study_raises_when_unsupported():
    operator = create_dicom_operator()
    operator.server.patient_root_move_support = False
    operator.server.study_root_move_support = False

    with pytest.raises(DicomError, match="does not support moving a study"):
        operator.move_study("1", "1.123", "DEST_AE")


@pytest.mark.django_db
def test_move_series_sends_c_move(mocker: MockerFixture):
    operator = create_dicom_operator()
    move_mock = mocker.patch.object(operator.dimse_connector, "send_c_move")

    operator.move_series("1", "1.123", "1.2.3.1", "DEST_AE")

    move_mock.assert_called_once()
    query, dest = move_mock.call_args.args
    assert query.QueryRetrieveLevel == "SERIES"
    assert query.SeriesInstanceUID == "1.2.3.1"
    assert dest == "DEST_AE"


@pytest.mark.django_db
def test_move_series_raises_when_unsupported():
    operator = create_dicom_operator()
    operator.server.patient_root_move_support = False
    operator.server.study_root_move_support = False

    with pytest.raises(DicomError, match="does not support moving a series"):
        operator.move_series("1", "1.123", "1.2.3.1", "DEST_AE")


# ---------------------------------------------------------------------------
# _fetch_images_with_c_get store handler (success + error abort path)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_with_c_get_store_handler_success(mocker: MockerFixture):
    """The store handler invokes the callback and returns the success status code."""
    operator = create_dicom_operator()
    captured: dict = {}

    def fake_send_c_get(query, store_handler, store_errors, *args, **kwargs):
        # Simulate pynetdicom firing the store handler with one event
        event = mocker.MagicMock()
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.4.1"
        event.dataset = ds
        event.file_meta = Dataset()
        captured["rc"] = store_handler(event, store_errors)

    mocker.patch.object(operator.dimse_connector, "send_c_get", side_effect=fake_send_c_get)

    received: list[Dataset] = []
    operator.fetch_series("1", "1.123", "1.2.3.1", received.append)

    assert captured["rc"] == 0x0000
    assert received[0].SOPInstanceUID == "1.2.4.1"


@pytest.mark.django_db
def test_fetch_with_c_get_store_handler_error_aborts_and_raises(mocker: MockerFixture):
    """A failing callback records the error, aborts the association, returns 0xA702,
    and the collected error is re-raised after send_c_get returns."""
    operator = create_dicom_operator()
    abort_mock = mocker.patch.object(operator.dimse_connector, "abort_connection")

    def bad_callback(ds: Dataset) -> None:
        raise ValueError("boom")

    def fake_send_c_get(query, store_handler, store_errors, *args, **kwargs):
        event = mocker.MagicMock()
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.4.1"
        event.dataset = ds
        event.file_meta = Dataset()
        rc = store_handler(event, store_errors)
        assert rc == 0xA702
        event.assoc.abort.assert_called_once()

    mocker.patch.object(operator.dimse_connector, "send_c_get", side_effect=fake_send_c_get)

    with pytest.raises(DicomError, match="Failed to handle image"):
        operator.fetch_series("1", "1.123", "1.2.3.1", bad_callback)

    abort_mock.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_fetched_image error mapping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_handle_fetched_image_out_of_space(mocker: MockerFixture):
    operator = create_dicom_operator()
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.4.1"

    def callback(_ds: Dataset) -> None:
        err = OSError("no space")
        err.errno = errno.ENOSPC
        err.filename = "/tmp/out.dcm"
        raise err

    with pytest.raises(DicomError, match="Out of disk space"):
        operator._handle_fetched_image(ds, callback)


@pytest.mark.django_db
def test_handle_fetched_image_generic_error(mocker: MockerFixture):
    operator = create_dicom_operator()
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.4.1"

    def callback(_ds: Dataset) -> None:
        raise RuntimeError("unexpected")

    with pytest.raises(DicomError, match="Failed to handle image '1.2.4.1'"):
        operator._handle_fetched_image(ds, callback)


# ---------------------------------------------------------------------------
# get_logs / close / abort
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_logs_aggregates_connector_logs(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.dimse_connector.logs = [{"level": "Warning", "title": "a", "message": "m1"}]
    operator.dicom_web_connector.logs = [{"level": "Warning", "title": "b", "message": "m2"}]
    operator.logs = [{"level": "Warning", "title": "c", "message": "m3"}]

    logs = operator.get_logs()

    assert [log["message"] for log in logs] == ["m1", "m2", "m3"]


@pytest.mark.django_db
def test_close_releases_open_association(mocker: MockerFixture):
    operator = create_dicom_operator()
    close_mock = mocker.patch.object(operator.dimse_connector, "close_connection")
    operator.dimse_connector.assoc = create_association_mock()

    operator.close()

    close_mock.assert_called_once()


@pytest.mark.django_db
def test_close_swallows_errors(mocker: MockerFixture):
    operator = create_dicom_operator()
    operator.dimse_connector.assoc = create_association_mock()
    mocker.patch.object(
        operator.dimse_connector, "close_connection", side_effect=RuntimeError("fail")
    )

    # Should not raise
    operator.close()


@pytest.mark.django_db
def test_abort_aborts_both_connectors(mocker: MockerFixture):
    operator = create_dicom_operator()
    dimse_abort = mocker.patch.object(operator.dimse_connector, "abort_connection")
    web_abort = mocker.patch.object(operator.dicom_web_connector, "abort")

    operator.abort()

    dimse_abort.assert_called_once()
    web_abort.assert_called_once()
