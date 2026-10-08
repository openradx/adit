import os

import pytest
from pytest_django.fixtures import Settings
from pytest_mock import MockerFixture

from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.file_transmit import FileReceivedHandler, FileTransmitClient
from adit.core.utils.testing_helpers import setup_dimse_orthancs

PATIENT_ID = "1005"
STUDY_UID = "1.2.840.113845.11.1000000001951524609.20200705173311.2689472"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db
def test_c_move_refetches_images_lost_on_the_way_to_the_worker(
    settings: Settings, mocker: MockerFixture
):
    # Arrange: a real C-MOVE from Orthanc through the receiver container; the worker loses
    # the first delivery of every second image of the series, at most half of them, which
    # the cap still allows to fetch again
    settings.C_MOVE_DOWNLOAD_TIMEOUT = 3
    settings.C_MOVE_REFETCH_ATTEMPTS = 2
    settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT = 50
    settings.C_MOVE_FAIL_ON_INCOMPLETE = True
    orthanc1, _ = setup_dimse_orthancs(cget_enabled=False)
    operator = DicomOperator(orthanc1)

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
    lost = set(image_uids[1::2])
    lost_before_refetch = set(lost)

    subscribe = FileTransmitClient.subscribe

    async def lossy_subscribe(
        client: FileTransmitClient,
        topic: str,
        file_received_handler: FileReceivedHandler,
        **kwargs,
    ):
        async def handle_received_file(filename: str, metadata: dict[str, str]):
            if metadata["SOPInstanceUID"] in lost:
                lost.remove(metadata["SOPInstanceUID"])
                os.remove(filename)
                return False
            return await file_received_handler(filename, metadata)  # type: ignore

        return await subscribe(client, topic, handle_received_file, **kwargs)

    mocker.patch.object(FileTransmitClient, "subscribe", lossy_subscribe)
    send_c_move = mocker.spy(operator.dimse_connector, "_send_c_move")
    received: list[str] = []

    # Act
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
