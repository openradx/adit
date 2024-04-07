import logging
from os import PathLike
from pathlib import Path

from adrf.views import sync_to_async
from pydicom import Dataset
from rest_framework.exceptions import NotFound

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import write_dataset

from ..errors import BadGatewayApiError, ServiceUnavailableApiError

logger = logging.getLogger("__name__")


async def wado_retrieve(
    source_server: DicomServer,
    query: dict[str, str],
    dest_folder: PathLike,
) -> None:
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)

    def callback(ds: Dataset) -> None:
        if ds is None:
            return

        folder_path = Path(dest_folder)
        file_name = f"{ds.SOPInstanceUID}.dcm"
        file_path = folder_path / file_name

        folder_path.mkdir(parents=True, exist_ok=True)
        write_dataset(ds, file_path)

    try:
        series_list = list(await sync_to_async(operator.find_series)(query_ds))

        if len(series_list) == 0:
            raise NotFound("No DICOM objects matches the query.")

        for series in series_list:
            await sync_to_async(operator.fetch_series)(
                patient_id=series.PatientID,
                study_uid=series.StudyInstanceUID,
                series_uid=series.SeriesInstanceUID,
                callback=callback,
            )
    except RetriableDicomError as err:
        logger.exception(err)
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        logger.exception(err)
        raise BadGatewayApiError(str(err))
