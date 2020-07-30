from functools import partial
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from main.models import DicomNode, DicomJob
from .models import AppSettings, BatchTransferJob, BatchTransferRequest
from .utils.batch_handler import BatchHandler
from .utils.task_utils import must_be_scheduled, next_batch_slot


def process_result(batch_job, result):
    """The callback to process a result of a running batch job.

    The callback returns True if the job should be paused or canceled.
    """
    request_id = result["RequestID"]
    request = BatchTransferRequest.objects.get(job=batch_job.id, request_id=request_id)
    if result["Status"] == BatchHandler.SUCCESS:
        request.status = BatchTransferRequest.Status.SUCCESS
    elif result["Status"] == BatchHandler.FAILURE:
        request.status = BatchTransferRequest.Status.FAILURE
    else:
        raise Exception("Invalid result status: " + result["Status"])
    request.message = result["Message"]
    if result["Pseudonym"]:
        result.pseudonym = result["Pseudonym"]
    request.processed_at = timezone.now()
    request.save()

    stop_processing = False

    if must_be_scheduled():
        batch_job.status = DicomJob.Status.PAUSED
        batch_job.paused_at = timezone.now()
        batch_job.save()
        stop_processing = True
    elif batch_job.status == DicomJob.Status.CANCELING:
        batch_job.status = DicomJob.Status.CANCELED
        batch_job.save()
        stop_processing = True

    return stop_processing


@shared_task
def batch_transfer_task(batch_job_id):
    """The background task to do the batch transfer."""
    batch_job = BatchTransferJob.objects.get(id=batch_job_id)

    if batch_job.status not in [DicomJob.Status.PENDING, DicomJob.Status.PAUSED]:
        raise Exception(
            f"Skipping task to process batch job with ID {batch_job.id} "
            f" because of an invalid status {batch_job.get_status_display()}."
        )

    batch_job.status = DicomJob.Status.IN_PROGRESS
    batch_job.started_at = timezone.now()
    batch_job.paused_at = None
    batch_job.save()

    source = batch_job.source.dicomserver  # Source is always a server
    app_settings = AppSettings.load()

    config = BatchHandler.Config(
        username=batch_job.created_by.username,
        client_ae_title=settings.ADIT_AE_TITLE,
        cache_folder=settings.ADIT_CACHE_FOLDER,
        source_ae_title=source.ae_title,
        source_ip=source.ip,
        source_port=source.port,
        patient_root_query_model_find=source.patient_root_query_model_find,
        patient_root_query_model_get=source.patient_root_query_model_get,
        pseudonymize=batch_job.pseudonymize,
        trial_protocol_id=batch_job.trial_protocol_id,
        trial_protocol_name=batch_job.trial_protocol_name,
        batch_timeout=app_settings.batch_timeout,
    )

    unprocessed_requests = [
        {
            "RequestID": req.request_id,
            "PatientID": req.patient_id,
            "PatientName": req.patient_name,
            "PatientBirthDate": req.patient_birth_date,
            "StudyDate": req.study_date,
            "Modality": req.modality,
            "Pseudonym": req.pseudonym,
        }
        for req in batch_job.get_unprocessed_requests()
    ]

    finished = False

    process_result_callback = partial(process_result, batch_job)

    # Destination can be a server or a folder
    if batch_job.destination.node_type == DicomNode.NodeType.SERVER:
        dest_server = batch_job.destination.dicomserver
        config.destination_ae_title = dest_server.ae_title
        config.destination_ip = dest_server.ip
        config.destination_port = dest_server.port

        handler = BatchHandler(config)
        finished = handler.batch_transfer(unprocessed_requests, process_result_callback)
    else:  # DicomNode.NodeType.Folder
        dest_folder = batch_job.destination.dicomfolder
        config.destination_folder = dest_folder.path

        handler = BatchHandler(config)
        finished = handler.batch_download(
            unprocessed_requests, process_result_callback, batch_job.archive_password
        )

    # If all requests were processed then the job finished otherwise it was
    # paused by the system or cancelled by the user
    if finished:
        total_requests = batch_job.requests.count()
        successful_requests = batch_job.get_successful_requests().count()
        if successful_requests == total_requests:
            batch_job.status = DicomJob.Status.SUCCESS
            batch_job.message = "All requests succeeded."
        elif successful_requests > 0:
            batch_job.status = DicomJob.Status.WARNING
            batch_job.message = "Some requests failed."
        else:
            batch_job.status = DicomJob.Status.FAILURE
            batch_job.message = "All requests failed."
        batch_job.save()
    elif batch_job.status == DicomJob.Status.PAUSED:
        batch_job.paused_at = timezone.now()
        batch_job.save()
        next_slot = next_batch_slot()
        batch_transfer_task.apply_async(args=[batch_job_id], eta=next_slot)
    elif batch_job.status == DicomJob.Status.CANCELED:
        batch_job.stopped_at = timezone.now()
        batch_job.save()
    else:
        raise Exception(
            f"Invalid status of job with ID {batch_job.id}:"
            f" {batch_job.get_status_display()}"
        )
