from typing import Literal

from adrf.views import sync_to_async
from pydicom import Dataset

from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import convert_query_dict_to_dataset


async def qido_find(
    source_server: DicomServer, query: dict[str, str], level: Literal["STUDY", "SERIES"]
) -> list[Dataset]:
    operator = DicomOperator(source_server)
    query_ds = convert_query_dict_to_dataset(query)

    if level == "STUDY":
        results = list(await sync_to_async(operator.find_studies)(query_ds))
    elif level == "SERIES":
        results = list(await sync_to_async(operator.find_series)(query_ds))
    else:
        raise ValueError(f"Invalid QIDO-RS level: {level}.")

    return results
