import logging
from typing import Literal

from adrf.views import sync_to_async

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator

from ..errors import BadGatewayApiError, ServiceUnavailableApiError

logger = logging.getLogger("__name__")


async def qido_find(
    source_server: DicomServer,
    query_ds: QueryDataset,
    limit_results: int | None,
    level: Literal["STUDY", "SERIES"],
) -> list[ResultDataset]:
    operator = DicomOperator(source_server)

    try:
        if level == "STUDY":
            results: list[ResultDataset] = list(
                await sync_to_async(operator.find_studies, thread_sensitive=False)(
                    query_ds, limit_results
                )
            )
        elif level == "SERIES":
            results: list[ResultDataset] = list(
                await sync_to_async(operator.find_series, thread_sensitive=False)(
                    query_ds, limit_results
                )
            )
        else:
            raise ValueError(f"Invalid QIDO-RS level: {level}.")
    except RetriableDicomError as err:
        logger.exception(err)
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        logger.exception(err)
        raise BadGatewayApiError(str(err))

    return results
