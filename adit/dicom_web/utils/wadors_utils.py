from os import PathLike

from adrf.views import sync_to_async
from rest_framework.exceptions import NotFound

from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_operator import DicomOperator


async def wado_retrieve(
    source_server: DicomServer,
    query: dict[str, str],
    dest_folder: PathLike,
) -> None:
    connector = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)

    series_list = list(await sync_to_async(connector.find_series)(query_ds))

    if len(series_list) == 0:
        raise NotFound("No DICOM objects matches the query.")

    for series in series_list:
        await sync_to_async(connector.download_series)(
            patient_id=series.PatientID,
            study_uid=series.StudyInstanceUID,
            series_uid=series.SeriesInstanceUID,
            dest_folder=dest_folder,
        )
