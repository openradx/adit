import json

import humanize
from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone

from adit.core.errors import RetriableTaskError
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.dicom_utils import format_datetime_attributes
from adit.core.utils.task_utils import hijack_logger, store_log_in_task
from adit.dicom_web.utils import DicomWebApi

from .models import DicomQidoJob, DicomQidoResult, DicomQidoTask

logger = get_task_logger(__name__)


def execute_qido(dicom_qido_task: DicomQidoTask, celery_task: AbortableCeleryTask) -> str:
    if dicom_qido_task.status == DicomQidoTask.Status.CANCELED:
        return dicom_qido_task.status

    if dicom_qido_task.status != DicomQidoTask.Status.PENDING:
        raise AssertionError(f"Invalid status {dicom_qido_task.status} of {dicom_qido_task}")

    dicom_qido_task.status = DicomQidoTask.Status.IN_PROGRESS
    dicom_qido_task.start = timezone.now()
    dicom_qido_task.save()

    logger.info("Started %s.", dicom_qido_task)

    handler, stream = hijack_logger(logger)

    dicom_qido_job: DicomQidoJob = dicom_qido_task.job

    try:
        if not dicom_qido_job.source.source_active:
            raise ValueError(f"Source DICOM node not active: {dicom_qido_job.source.name}")

        _c_find_to_result(dicom_qido_task)

        dicom_qido_task.status = DicomQidoTask.Status.SUCCESS
        dicom_qido_task.message = "Query task completed successfully."
        dicom_qido_task.end = timezone.now()

    except RetriableTaskError as err:
        logger.exception("Retriable error occurred during %s.", dicom_qido_task)

        # We can't use the Celery built-in max_retries and celery_task.request.retries
        # directly as we also use celery_task.retry() for scheduling tasks.
        if dicom_qido_task.retries < settings.TRANSFER_TASK_RETRIES:
            logger.info("Retrying task in %s.", humanize.naturaldelta(err.delay))
            dicom_qido_task.status = DicomQidoTask.Status.PENDING
            dicom_qido_task.message = "Task timed out and will be retried."
            dicom_qido_task.retries += 1

            # Increase the priority slightly to make sure images that were moved
            # from the GE archive storage to the fast access storage are still there
            # when we retry.
            priority = celery_task.request.delivery_info["priority"]
            if priority < settings.CELERY_TASK_QUEUE_MAX_PRIORITY:
                priority += 1

            raise celery_task.retry(eta=timezone.now() + err.delay, exc=err, priority=priority)

        logger.error("No more retries for finally failed %s.", dicom_qido_task)
        dicom_qido_task.status = DicomQidoTask.Status.FAILURE
        dicom_qido_task.message = str(err)
        dicom_qido_task.end = timezone.now()

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Unrecoverable failure occurred in %s.", dicom_qido_task)
        dicom_qido_task.status = DicomQidoTask.Status.FAILURE
        dicom_qido_task.message = str(err)
        dicom_qido_task.end = timezone.now()

    finally:
        store_log_in_task(logger, handler, stream, dicom_qido_task)
        dicom_qido_task.save()

    return dicom_qido_task.status


def _c_find_to_result(dicom_qido_task: DicomQidoTask) -> None:
    connector = DicomConnector(dicom_qido_task.job.source.dicomserver)

    dicom_web_api = DicomWebApi(connector)

    query = _create_query(dicom_qido_task)
    if dicom_qido_task.job.level == "STUDY":
        c_find_result = dicom_web_api.qido_find_studies(query)
    elif dicom_qido_task.job.level == "SERIES":
        c_find_result = dicom_web_api.qido_find_series(query)
    else:
        raise ValueError(f"Invalid job level: {dicom_qido_task.job.level}")

    if len(c_find_result) <= 0:
        raise ValueError("No query results found.")

    result = DicomQidoResult(
        job=dicom_qido_task.job,
        query_results=json.dumps(c_find_result, default=str),
    )
    result.save()


def _create_query(dicom_task: DicomQidoTask) -> dict:
    query = {
        "StudyInstanceUID": dicom_task.study_uid,
        "SeriesInstanceUID": dicom_task.series_uid,
        "PatientID": "",
        "PatientName": "",
        "PatientBirthDate": "",
        "PatientSex": "",
        "AccessionNumber": "",
        "StudyDate": "",
        "StudyTime": "",
        "ModalitiesInStudy": "",
        "Modality": "",
        "NumberOfStudyRelatedInstances": "",
        "NumberOfSeriesRelatedInstances": "",
        "SOPInstaceUID": "",
        "StudyDescription": "",
        "SeriesDescription": "",
        "SeriesNumber": "",
    }

    request_query = eval(dicom_task.query)
    for attribute, value in request_query.items():
        query[attribute] = value

    query = format_datetime_attributes([query])[0]

    return query
