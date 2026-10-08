import logging
import os
import threading
import time
from collections.abc import Callable

import pytest
from pytest_django.fixtures import Settings
from pytest_mock import MockerFixture

from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.file_transmit import FileReceivedHandler, FileTransmitClient
from adit.core.utils.orthanc_utils import OrthancRestHandler
from adit.core.utils.testing_helpers import setup_dimse_orthancs

PATIENT_ID = "1005"
STUDY_UID = "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"


def _setup_operator(settings: Settings, download_timeout: int) -> DicomOperator:
    settings.C_MOVE_DOWNLOAD_TIMEOUT = download_timeout
    settings.C_MOVE_SYNC_TIMEOUT = 120
    settings.C_MOVE_REFETCH_ATTEMPTS = 2
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = 50
    settings.C_MOVE_FAIL_ON_INCOMPLETE = True
    orthanc1, _ = setup_dimse_orthancs(cget_enabled=False)
    return DicomOperator(orthanc1)


def _largest_series(operator: DicomOperator) -> tuple[str, list[str]]:
    image_uids_by_series = {
        series.SeriesInstanceUID: [
            image.SOPInstanceUID
            for image in operator.find_images(
                QueryDataset.create(
                    PatientID=PATIENT_ID,
                    StudyInstanceUID=STUDY_UID,
                    SeriesInstanceUID=series.SeriesInstanceUID,
                )
            )
        ]
        for series in list(
            operator.find_series(
                QueryDataset.create(PatientID=PATIENT_ID, StudyInstanceUID=STUDY_UID)
            )
        )
    }
    series_uid, image_uids = max(image_uids_by_series.items(), key=lambda item: len(item[1]))
    assert len(image_uids) >= 2
    return series_uid, image_uids


def _lose_first_deliveries(
    mocker: MockerFixture, lost: set[str], on_synced: Callable[[], None] | None = None
) -> None:
    """The worker loses the first delivery of the `lost` images on the way from the receiver;
    `on_synced` runs after each confirmation of the receiver."""
    subscribe = FileTransmitClient.subscribe

    async def lossy_subscribe(
        client: FileTransmitClient,
        topic: str,
        file_received_handler: FileReceivedHandler,
        synced_handler=None,
        **kwargs,
    ):
        async def handle_received_file(filename: str, metadata: dict[str, str]):
            if metadata["SOPInstanceUID"] in lost:
                lost.remove(metadata["SOPInstanceUID"])
                os.remove(filename)
                return False
            return await file_received_handler(filename, metadata)  # type: ignore

        def handle_synced(token: str):
            assert synced_handler
            synced_handler(token)
            if on_synced:
                on_synced()

        return await subscribe(
            client, topic, handle_received_file, synced_handler=handle_synced, **kwargs
        )

    mocker.patch.object(FileTransmitClient, "subscribe", lossy_subscribe)


def _log_messages(caplog: pytest.LogCaptureFixture, text: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if text in record.getMessage()]


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db
def test_c_move_refetches_images_lost_on_the_way_to_the_worker(
    settings: Settings, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    # Arrange: a real C-MOVE from Orthanc through the receiver container; the worker loses
    # the first delivery of every second image of the series, at most half of them, which
    # the cap still allows to fetch again
    operator = _setup_operator(settings, download_timeout=3)
    series_uid, image_uids = _largest_series(operator)
    lost = set(image_uids[1::2])
    lost_before_refetch = set(lost)
    _lose_first_deliveries(mocker, lost)
    send_c_move = mocker.spy(operator.dimse_connector, "_send_c_move")
    received: list[str] = []

    # Act
    with caplog.at_level(logging.INFO):
        operator.fetch_series(
            PATIENT_ID, STUDY_UID, series_uid, lambda ds: received.append(ds.SOPInstanceUID)
        )

    # Assert: all images arrived, the lost ones through one IMAGE-level C-MOVE each
    assert sorted(received) == sorted(image_uids)
    assert not lost
    refetched = [
        (call.args[0].QueryRetrieveLevel, call.args[0].SOPInstanceUID)
        for call in send_c_move.call_args_list
        if call.args[0].get("SOPInstanceUID")
    ]
    assert sorted(refetched) == sorted(("IMAGE", image_uid) for image_uid in lost_before_refetch)
    assert not _log_messages(caplog, "arrived after the receiver confirmed")


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db
def test_c_move_tolerates_an_image_the_pacs_sends_after_the_move(
    settings: Settings, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    # Arrange: the worker loses the first delivery of one image, and Orthanc sends it again
    # through the receiver only after the receiver confirmed the delivery, as a PACS with an
    # asynchronous C-MOVE does
    operator = _setup_operator(settings, download_timeout=5)
    series_uid, image_uids = _largest_series(operator)
    late_image = image_uids[1]
    orthanc = OrthancRestHandler(settings.ORTHANC1_HOST, settings.ORTHANC1_HTTP_PORT)
    [late_image_id] = orthanc.find({"Level": "Instance", "Query": {"SOPInstanceUID": late_image}})
    push_errors: list[Exception] = []
    pushes: list[threading.Thread] = []

    def push_late_image():
        # Later than a sync takes, well within the grace
        time.sleep(1.5)
        try:
            response = orthanc.session.post(
                f"http://{orthanc.host}:{orthanc.port}/modalities/ADIT/store",
                json={"Resources": [late_image_id], "Synchronous": True},
            )
            response.raise_for_status()
        except Exception as err:
            push_errors.append(err)

    def on_synced():
        # Not on the consumer's event loop, which must keep reading meanwhile
        if not pushes:
            pushes.append(threading.Thread(target=push_late_image))
            pushes[0].start()

    lost = {late_image}
    _lose_first_deliveries(mocker, lost, on_synced)
    send_c_move = mocker.spy(operator.dimse_connector, "_send_c_move")
    received: list[str] = []

    # Act
    try:
        with caplog.at_level(logging.INFO):
            operator.fetch_series(
                PATIENT_ID, STUDY_UID, series_uid, lambda ds: received.append(ds.SOPInstanceUID)
            )
    finally:
        for push in pushes:
            push.join()

    # Assert: the late image arrived during the grace, without an IMAGE-level C-MOVE
    assert not push_errors
    assert sorted(received) == sorted(image_uids)
    assert not lost
    assert not [call for call in send_c_move.call_args_list if call.args[0].get("SOPInstanceUID")]
    assert len(_log_messages(caplog, "arrived after the receiver confirmed")) == 1
