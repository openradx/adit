from django.conf import settings
from functools import partial
from datetime import datetime, time, timedelta
import django_rq
from .models import AppSettings, BatchTransferJob, BatchTransferRequest
from main.models import DicomNode, DicomServer
from .utils.batch_handler import BatchHandler

def is_time_between(begin_time, end_time, check_time=datetime.now().time()):
    """Adapted from https://stackoverflow.com/a/10048290/166229"""

    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

def must_be_scheduled():
    app_settings = AppSettings.objects.first()
    paused = app_settings.batch_transfer_paused
    begin_time = app_settings.batch_slot_begin_time
    end_time = app_settings.batch_slot_end_time
    return paused or not is_time_between(begin_time, end_time)

def next_batch_slot():
    from_time = settings.BATCH_TRANSFER_JOB_FROM_TIME
    now = datetime.now()
    if now.time < from_time:
        return datetime.combine(now.date(), from_time)
    else:
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, from_time)    

def enqueue_batch_job(batch_job_id, eta=None):
    if eta or must_be_scheduled():
        if eta is None:
            eta = next_batch_slot()
        scheduler = django_rq.get_scheduler('batch_transfer')
        scheduler.enqueue_at(eta, batch_transfer, batch_job_id)
    else:
        queue = django_rq.get_queue('batch_transfer')
        queue.enqueue(batch_transfer, batch_job_id)

def _process_result(batch_job_id, result):
    request_id = result['RequestID']
    request = BatchTransferRequest.objects.get(
            job=batch_job_id, request_id=request_id)
    if result['Status'] == BatchHandler.SUCCESS:
        request.status = BatchTransferRequest.Status.SUCCESS
    elif result['Status'] == BatchHandler.ERROR:
        request.status = BatchTransferRequest.Status.ERROR
    else:
        raise Exception('Invalid result status: ' + result['Status'])
    request.message = result['Message']
    if result['Pseudonym']:
        result.pseudonym = result['Pseudonym']
    result.processed_at = datetime.now()
    result.save()

    if must_be_scheduled():
        enqueue_batch_job(batch_job_id, eta=next_batch_slot())
        return True # stops further processing

    return False

def batch_transfer(batch_job_id):
    batch_job = BatchTransferJob.objects.select_related().get(id=batch_job_id)
    user = batch_job.created_by
    source = batch_job.source.dicomserver # Source is always a server

    config = BatchHandler.Config(
        username = user.username,
        client_ae_title = settings.ADIT_AE_TITLE,
        cache_folder = settings.BATCH_TRANSFER_CACHE_FOLDER,
        source_ae_title = source.ae_title,
        source_ip = source.ip,
        source_port = source.port,
        patient_root_query_model_find = (source.find_query_model 
                == DicomServer.QueryModel.PATIENT_ROOT),
        patient_root_query_model_get = (source.get_query_model 
                == DicomServer.QueryModel.PATIENT_ROOT),
        pseudonymize = batch_job.pseudonymize,
        trial_protocol_id = batch_job.trial_protocol_id,
        trial_protocol_name = batch_job.trial_protocol_name
    )

    unprocessed_requests = map(lambda req: {
        'RequestID': req.request_id,
        'PatientID': req.patient_id,
        'PatientName': req.patient_name,
        'PatientBirthDate': req.patient_birth_date,
        'StudyDate': req.study_date,
        'Modality': req.modality,
        'Pseudonym': req.pseudonym
    }, batch_job.requests.filter(status=BatchTransferRequest.Status.UNPROCESSED))

    process_result_callback = partial(_process_result, batch_job.id)

    # Destination can be a server or a folder
    if batch_job.destination.node_type == DicomNode.NodeType.SERVER:
        dest_server = batch_job.destination.dicomserver
        config.destination_ae_title = dest_server.ae_title
        config.destination_ip = dest_server.ip
        config.destination_port = dest_server.port

        handler = BatchHandler(config)
        handler.batch_transfer(unprocessed_requests, process_result_callback)
    else: # DicomNode.NodeType.Folder
        dest_folder = batch_job.destination.dicomfolder
        config.destination_folder = dest_folder.path
        # TODO configuration for creating an archive

        handler = BatchHandler(config)
        handler.batch_download(unprocessed_requests, process_result_callback)
