from django.conf import settings
import logging
from celery import shared_task
from functools import partial
from django.utils import timezone
from datetime import datetime, time, timedelta
from main.models import DicomNode, DicomServer, DicomJob
from .models import AppSettings, BatchTransferJob, BatchTransferRequest
from .utils.batch_handler import BatchHandler

def is_time_between(begin_time, end_time, check_time):
    """Checks if a given time is between two other times.

    If the time to check is not provided then use the current time.    
    Adapted from https://stackoverflow.com/a/10048290/166229
    """
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

def must_be_scheduled():
    """Checks if the batch job can run now or must be scheduled.

    In the dynamic site settings a time slot is specified when the
    batch transfer jobs should run. The job processing could also be
    suspended in the settings.
    """
    app_settings = AppSettings.load()
    suspended = app_settings.batch_transfer_suspended
    begin_time = app_settings.batch_slot_begin_time
    end_time = app_settings.batch_slot_end_time
    check_time = timezone.now().time()
    return suspended or not is_time_between(begin_time, end_time, check_time)

def next_batch_slot():
    """Return the next datetime slot when a batch job can be processed."""
    app_settings = AppSettings.load()
    begin_time = app_settings.batch_slot_begin_time
    now = timezone.now()
    if now.time() < begin_time:
        return datetime.combine(now.date(), begin_time)
    else:
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, begin_time)    

def process_result(batch_job, result):
    """The callback to process a result of a running batch job.

    The callback returns True if the job should be paused or canceled.
    """
    request_id = result['RequestID']
    request = BatchTransferRequest.objects.get(
            job=batch_job.id, request_id=request_id)
    if result['Status'] == BatchHandler.SUCCESS:
        request.status = BatchTransferRequest.Status.SUCCESS
    elif result['Status'] == BatchHandler.ERROR:
        request.status = BatchTransferRequest.Status.ERROR
    else:
        raise Exception('Invalid result status: ' + result['Status'])
    request.message = result['Message']
    if result['Pseudonym']:
        result.pseudonym = result['Pseudonym']
    request.processed_at = timezone.now()
    request.save()

    if must_be_scheduled():
        batch_job.status = DicomJob.Status.PAUSED
        batch_job.save()
        return True # pause further processing for now
    elif batch_job.status == DicomJob.Status.CANCELING:
        batch_job.status = DicomJob.Status.CANCELED
        batch_job.save()
        return True # cancel further processing

    return False

def enqueue_batch_job(batch_job_id, eta=None):
    """Enqueue a batch transfer job.

    If we are in a time slot for batch transfers then the job is directly
    enqueued, otherwise it is scheduled for the next slot.
    """
    if eta or must_be_scheduled():
        if eta is None:
            eta = next_batch_slot()
        batch_transfer_task.apply_async(args=[batch_job_id], eta=eta)
    else:
        batch_transfer_task.delay(batch_job_id)

@shared_task
def batch_transfer_task(batch_job_id):
    """The background task to do the batch transfer."""
    batch_job = BatchTransferJob.objects.get(id=batch_job_id)

    if batch_job.status not in [DicomJob.Status.PENDING, DicomJob.Status.PAUSED]:
        raise Exception(f'Skipping task to process batch job with ID {batch_job.id} '
                f' because of an invalid status {batch_job.get_status_display()}.')

    batch_job.status = DicomJob.Status.IN_PROGRESS
    batch_job.save()

    source = batch_job.source.dicomserver # Source is always a server
    app_settings = AppSettings.load()

    config = BatchHandler.Config(
        username=batch_job.created_by.username,
        client_ae_title=settings.ADIT_AE_TITLE,
        cache_folder=settings.BATCH_TRANSFER_CACHE_FOLDER,
        source_ae_title=source.ae_title,
        source_ip=source.ip,
        source_port=source.port,
        patient_root_query_model_find=source.patient_root_query_model_find,
        patient_root_query_model_get=source.patient_root_query_model_get,
        pseudonymize=batch_job.pseudonymize,
        trial_protocol_id=batch_job.trial_protocol_id,
        trial_protocol_name=batch_job.trial_protocol_name,
        batch_timeout=app_settings.batch_timeout
    )

    unprocessed_requests = [{
        'RequestID': req.request_id,
        'PatientID': req.patient_id,
        'PatientName': req.patient_name,
        'PatientBirthDate': req.patient_birth_date,
        'StudyDate': req.study_date,
        'Modality': req.modality,
        'Pseudonym': req.pseudonym
    } for req in batch_job.get_unprocessed_requests()]

    batch_job.status = DicomJob.Status.IN_PROGRESS
    batch_job.save()

    complete = False

    process_result_callback = partial(process_result, batch_job)
    
    # Destination can be a server or a folder
    if batch_job.destination.node_type == DicomNode.NodeType.SERVER:
        dest_server = batch_job.destination.dicomserver
        config.destination_ae_title = dest_server.ae_title
        config.destination_ip = dest_server.ip
        config.destination_port = dest_server.port

        handler = BatchHandler(config)
        complete = handler.batch_transfer(unprocessed_requests, process_result_callback)
    else: # DicomNode.NodeType.Folder
        dest_folder = batch_job.destination.dicomfolder
        config.destination_folder = dest_folder.path

        handler = BatchHandler(config)
        complete = handler.batch_download(unprocessed_requests, 
                process_result_callback, batch_job.archive_password)

    # If all requests were processed then the job completed otherwise it is
    # paused or was cancelled by the user
    if complete:
        batch_job.status = DicomJob.Status.COMPLETED
        batch_job.save()
    elif batch_job.status == DicomJob.Status.PAUSED:
        enqueue_batch_job(batch_job.id, eta=next_batch_slot())
    elif batch_job.status != DicomJob.Status.CANCELED:
        raise Exception('Invalid job status while processing task: ' \
                + batch_job.get_status_display())
