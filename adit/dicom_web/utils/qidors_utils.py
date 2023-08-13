from typing import Literal

from adrf.views import sync_to_async

from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator


async def qido_find(
    source_server: DicomServer, query: dict[str, str], level: Literal["STUDY", "SERIES"]
) -> list[ResultDataset]:
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)

    if level == "STUDY":
        results = list(await sync_to_async(operator.find_studies)(query_ds))
    elif level == "SERIES":
        results = list(await sync_to_async(operator.find_series)(query_ds))
    else:
        raise ValueError(f"Invalid QIDO-RS level: {level}.")

    return results
