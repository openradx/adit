from os import PathLike

from adrf.views import sync_to_async
from celery.utils.log import get_task_logger
from rest_framework.exceptions import NotFound

from adit.core.models import DicomServer
from adit.core.utils.dicom_connector import DicomConnector

logger = get_task_logger(__name__)


async def wado_retrieve(source_server: DicomServer, query: dict, dest_folder: PathLike) -> None:
    connector = DicomConnector(source_server)

    logger.info("Connected to server %s.", source_server.ae_title)

    series_list = await sync_to_async(connector.find_series)(query)

    if len(series_list) < 1:
        raise NotFound("No dicom objects matching the query exist.")

    for series in series_list:
        series_uid = series["SeriesInstanceUID"]
        await sync_to_async(connector.download_series)(
            patient_id="",
            study_uid=query["StudyInstanceUID"],
            series_uid=series_uid,
            dest_folder=dest_folder,
        )
