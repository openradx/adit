import asyncio
import logging
from typing import AsyncIterator

from adrf.views import sync_to_async
from pydicom import Dataset
from rest_framework.exceptions import NotFound

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator

from ..errors import BadGatewayApiError, ServiceUnavailableApiError

logger = logging.getLogger("__name__")


async def wado_retrieve(
    source_server: DicomServer,
    query: dict[str, str],
) -> AsyncIterator[Dataset]:
    """WADO retrieve helper.

    Mainly converts a sync callback (by the operator) to an async iterator.
    """
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue[Dataset]()

    def callback(ds: Dataset) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ds)

    try:
        series_list = list(
            await sync_to_async(operator.find_series, thread_sensitive=False)(query_ds)
        )

        if len(series_list) == 0:
            raise NotFound("No DICOM objects matches the query.")

        for series in series_list:
            fetch_series_task = asyncio.create_task(
                sync_to_async(operator.fetch_series, thread_sensitive=False)(
                    patient_id=series.PatientID,
                    study_uid=series.StudyInstanceUID,
                    series_uid=series.SeriesInstanceUID,
                    callback=callback,
                )
            )

            while True:
                queue_get_task = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    [fetch_series_task, queue_get_task], return_when=asyncio.FIRST_COMPLETED
                )

                finished = False
                for task in done:
                    if task == queue_get_task:
                        yield queue_get_task.result()
                    if task == fetch_series_task:
                        finished = True

                if finished:
                    queue_get_task.cancel()
                    break

            await asyncio.wait([fetch_series_task, queue_get_task])

    except RetriableDicomError as err:
        logger.exception(err)
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        logger.exception(err)
        raise BadGatewayApiError(str(err))
