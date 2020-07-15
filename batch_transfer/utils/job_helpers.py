from datetime import datetime, time, timedelta
from django.conf import settings
import django_rq
from ..jobs import batch_transfer

def is_time_between(begin_time, end_time, check_time):
    """Adapted from https://stackoverflow.com/a/10048290/166229"""

    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

def must_be_scheduled():
    from_time = settings.BATCH_TRANSFER_JOB_FROM_TIME
    till_time = settings.BATCH_TRANSFER_JOB_TILL_TIME
    current_time = datetime.now().time()
    return not is_time_between(from_time, till_time, current_time)

def next_datetime_batch_slot():
    from_time = settings.BATCH_TRANSFER_JOB_FROM_TIME
    now = datetime.now()
    if now.time < from_time:
        return datetime.combine(now.date(), from_time)
    else:
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, from_time)    

def enqueue_batch_job(batch_job_id):
    if must_be_scheduled():
        scheduler = django_rq.get_scheduler('batch_transfer')
        scheduler.enqueue_at(next_datetime_batch_slot(),
                batch_transfer,batch_job_id)
    else:
        queue = django_rq.get_queue('batch_transfer')
        queue.enqueue(batch_transfer, batch_job_id)
