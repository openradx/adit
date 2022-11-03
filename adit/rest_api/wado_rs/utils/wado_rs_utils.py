from time import timezone
from ...utils.dicom_web_utils import DicomWebApi
from ...serializers import DicomWebSerializer
from adit.core.utils.task_utils import hijack_logger, store_log_in_task
from adit.core.errors import RetriableTaskError
from celery import Task as CeleryTask
import humanize
from ..models import DicomWadoTask, DicomWadoJob
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import EmptyResultSet
from celery.utils.log import get_task_logger
from adit.core.utils.dicom_connector import DicomConnector
from adit.xnat_support.utils.xnat_connector import XnatConnector


logger = get_task_logger(__name__)


def execute_wado(
    dicom_wado_task: DicomWadoTask, celery_task: CeleryTask
) -> DicomWadoTask.Status:
    if dicom_wado_task.status == DicomWadoTask.Status.CANCELED:
        return dicom_wado_task.status

    if dicom_wado_task.status != DicomWadoTask.Status.PENDING:
        raise AssertionError(
            f"Invalid status {dicom_wado_task.status} of {dicom_wado_task}"
        )

    dicom_wado_task.status = DicomWadoTask.Status.IN_PROGRESS
    dicom_wado_task.start = timezone.now()
    dicom_wado_task.save()

    logger.info("Started %s.", dicom_wado_task)

    handler, stream = hijack_logger(logger)

    dicom_wado_job: DicomWadoJob = dicom_wado_task.job

    try:
        if not dicom_wado_job.source.source_active:
            raise ValueError(
                f"Source DICOM node not active: {dicom_wado_job.source.name}"
            )

        _serialize_and_transfer_to_adit(dicom_wado_task)

        dicom_wado_task.status = DicomWadoTask.Status.SUCCESS
        dicom_wado_task.message = "Transfer task completed successfully."
        dicom_wado_task.end = timezone.now()

    except RetriableTaskError as err:
        logger.exception("Retriable error occurred during %s.", dicom_wado_task)

        # We can't use the Celery built-in max_retries and celery_task.request.retries
        # directly as we also use celery_task.retry() for scheduling tasks.
        if dicom_wado_task.retries < settings.TRANSFER_TASK_RETRIES:
            logger.info("Retrying task in %s.", humanize.naturaldelta(err.delay))
            dicom_wado_task.status = DicomWadoTask.Status.PENDING
            dicom_wado_task.message = "Task timed out and will be retried."
            dicom_wado_task.retries += 1

            # Increase the priority slightly to make sure images that were moved
            # from the GE archive storage to the fast access storage are still there
            # when we retry.
            priority = celery_task.request.delivery_info["priority"]
            if priority < settings.CELERY_TASK_QUEUE_MAX_PRIORITY:
                priority += 1

            raise celery_task.retry(
                eta=timezone.now() + err.delay, exc=err, priority=priority
            )

        logger.error("No more retries for finally failed %s.", dicom_wado_task)
        dicom_wado_task.status = DicomWadoTask.Status.FAILURE
        dicom_wado_task.message = str(err)
        dicom_wado_task.end = timezone.now()

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Unrecoverable failure occurred in %s.", dicom_wado_task)
        dicom_wado_task.status = DicomWadoTask.Status.FAILURE
        dicom_wado_task.message = str(err)
        dicom_wado_task.end = timezone.now()

    finally:
        store_log_in_task(logger, handler, stream, dicom_wado_task)
        dicom_wado_task.save()

    return dicom_wado_task.status
    
    
def _create_query(
    dicom_wado_task: DicomWadoTask
) -> dict:
    query = {
        "StudyInstanceUID": dicom_wado_task.study_uid,
        "SeriesInstanceUID": dicom_wado_task.series_uid,
    }
    return query


def _serialize_and_transfer_to_adit(
    dicom_wado_task: DicomWadoTask
) -> None:
    query = _create_query(dicom_wado_task)
    serializer = DicomWebSerializer()
    serializer.setup_writer(       
        dicom_wado_task.job.file_path,
        dicom_wado_task.job.mode,
        dicom_wado_task.job.content_type,
        dicom_wado_task.job.boundary,
    )

    logger.info("Set up a serializer and writer for content type %s.", dicom_wado_task.job.content_type)

    if dicom_wado_task.job.source.dicomserver.xnat_rest_source:
        connector = XnatConnector(dicom_wado_task.job.source.dicomserver)
    else:
        connector = DicomConnector(dicom_wado_task.job.source.dicomserver)
    
    dicom_web_api = DicomWebApi(connector)

    logger.info("Connected to server %s.", dicom_wado_task.job.source.dicomserver.ae_title)

    series_list = connector.find_series(query)
    
    if len(series_list)<1:
        raise EmptyResultSet(f"No dicom objects matching the query exist.")

    file_path = dicom_wado_task.job.file_path

    serializer.start_file(file_path, dicom_wado_task.job.content_type)
    dicom_web_api.wado_download_study(
        dicom_wado_task.study_uid,
        series_list,
        dicom_wado_task.job.mode,
        dicom_wado_task.job.content_type,
        dicom_wado_task.job.folder_path,
        serializer,
    )
    serializer.end_file(file_path, dicom_wado_task.job.content_type)

