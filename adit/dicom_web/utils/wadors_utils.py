import asyncio
import logging
from typing import AsyncIterator, Literal

from adrf.views import sync_to_async
from pydicom import Dataset

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator

from ..errors import BadGatewayApiError, ServiceUnavailableApiError

logger = logging.getLogger("__name__")


async def wado_retrieve(
    source_server: DicomServer,
    query: dict[str, str],
    level: Literal["STUDY", "SERIES", "IMAGE"],
    pseudonym: str | None = None,
    trial_protocol_id: str | None = None,
    trial_protocol_name: str | None = None,
) -> AsyncIterator[Dataset]:
    """WADO retrieve helper.

    Mainly converts a sync callback (by the operator) to an async iterator.
    """
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue[Dataset]()

    dicom_manipulator = DicomManipulator()

    def callback(ds: Dataset) -> None:
        dicom_manipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)

        loop.call_soon_threadsafe(queue.put_nowait, ds)

    def _handle_dataset(ds: Dataset) -> None:
        pseudonymizer.pseudonymize(ds)

        if trial_protocol_id is not None:
            ds.ClinicalTrialProtocolID = trial_protocol_id

        if trial_protocol_name is not None:
            ds.ClinicalTrialProtocolName = trial_protocol_name

    try:
        if level == "STUDY":
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_study, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    callback=callback,
                )
            )
        elif level == "SERIES":
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_series, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    series_uid=query_ds.SeriesInstanceUID,
                    callback=callback,
                )
            )
        elif level == "IMAGE":
            assert query_ds.has("SeriesInstanceUID")
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_image, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    series_uid=query_ds.SeriesInstanceUID,
                    image_uid=query_ds.SOPInstanceUID,
                    callback=callback,
                )
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")

        while True:
            queue_get_task = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                [fetch_task, queue_get_task], return_when=asyncio.FIRST_COMPLETED
            )

            finished = False
            for task in done:
                if task == queue_get_task:
                    yield queue_get_task.result()
                if task == fetch_task:
                    finished = True

            if finished:
                queue_get_task.cancel()
                break

        await asyncio.wait([fetch_task, queue_get_task])

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))
