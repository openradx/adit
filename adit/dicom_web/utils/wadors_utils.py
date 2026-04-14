import asyncio
import logging
from collections.abc import Callable
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
    queue: asyncio.Queue[Dataset | None] = asyncio.Queue()

    dicom_manipulator = DicomManipulator()

    def callback(ds: Dataset) -> None:
        dicom_manipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)
        loop.call_soon_threadsafe(queue.put_nowait, ds)

    def fetch_with_sentinel(fetch_func: Callable[..., None], **kwargs: object) -> None:
        """Wrapper that calls fetch function and schedules sentinel afterward.

        By scheduling the sentinel via call_soon_threadsafe from within the same
        thread (after the sync function completes), we guarantee FIFO ordering:
        all data callbacks scheduled during fetch will be processed before the
        sentinel because they were scheduled first.
        """
        try:
            fetch_func(**kwargs)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    try:
        if level == "STUDY":
            fetch_coro = sync_to_async(fetch_with_sentinel, thread_sensitive=False)(
                operator.fetch_study,
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                callback=callback,
            )
        elif level == "SERIES":
            fetch_coro = sync_to_async(fetch_with_sentinel, thread_sensitive=False)(
                operator.fetch_series,
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                series_uid=query_ds.SeriesInstanceUID,
                callback=callback,
            )
        elif level == "IMAGE":
            assert query_ds.has("SeriesInstanceUID")
            fetch_coro = sync_to_async(fetch_with_sentinel, thread_sensitive=False)(
                operator.fetch_image,
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                series_uid=query_ds.SeriesInstanceUID,
                image_uid=query_ds.SOPInstanceUID,
                callback=callback,
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")

        # Start fetch task. Sentinel will be added via call_soon_threadsafe when done.
        fetch_task = asyncio.create_task(fetch_coro)

        sentinel_received = False
        try:
            while True:
                queue_ds = await queue.get()
                if queue_ds is None:
                    sentinel_received = True
                    break
                yield queue_ds
        finally:
            # Only cancel if the consumer stopped early (not via sentinel).
            # When the sentinel was received, the fetch function has already
            # completed and its exception must be propagated, not cancelled.
            if not sentinel_received and not fetch_task.done():
                fetch_task.cancel()
            try:
                await fetch_task
            except asyncio.CancelledError:
                pass

    except RetriableDicomError as exc:
        raise ServiceUnavailableApiError(str(exc))
    except DicomError as exc:
        raise BadGatewayApiError(str(exc))
