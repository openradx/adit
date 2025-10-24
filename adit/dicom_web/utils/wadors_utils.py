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
    queue = asyncio.Queue[Dataset | None]()

    dicom_manipulator = DicomManipulator()

    def callback(ds: Dataset) -> None:
        dicom_manipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)
        loop.call_soon_threadsafe(queue.put_nowait, ds)

    try:
        if level == "STUDY":
            fetch_coro = sync_to_async(operator.fetch_study, thread_sensitive=False)(
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                callback=callback,
            )
        elif level == "SERIES":
            fetch_coro = sync_to_async(operator.fetch_series, thread_sensitive=False)(
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                series_uid=query_ds.SeriesInstanceUID,
                callback=callback,
            )
        elif level == "IMAGE":
            assert query_ds.has("SeriesInstanceUID")
            fetch_coro = sync_to_async(operator.fetch_image, thread_sensitive=False)(
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                series_uid=query_ds.SeriesInstanceUID,
                image_uid=query_ds.SOPInstanceUID,
                callback=callback,
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")

        async def add_sentinel_when_done(task: asyncio.Task[None]) -> None:
            try:
                await task
            finally:
                await queue.put(None)

        async with asyncio.TaskGroup() as task_group:
            fetch_task = task_group.create_task(fetch_coro)
            task_group.create_task(add_sentinel_when_done(fetch_task))

            while True:
                queue_ds = await queue.get()
                if queue_ds is None:
                    break
                yield queue_ds

    except ExceptionGroup as eg:
        # Extract the first relevant exception
        for exc in eg.exceptions:
            if isinstance(exc, RetriableDicomError):
                raise ServiceUnavailableApiError(str(exc))
            if isinstance(exc, DicomError):
                raise BadGatewayApiError(str(exc))
        raise  # Re-raise if no handled exception found
