from datetime import datetime, time
from django.conf import settings
import django_rq

def is_time_between(begin_time, end_time, check_time):
    """Adapted from https://stackoverflow.com/a/10048290/166229"""

    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

def enqueue_batch_job(batch_job_id):
    scheduler = django_rq.get_scheduler('low')
    from_time = settings.BATCH_TRANSFER_JOB_FROM_TIME
    till_time = settings.BATCH_TRANSFER_JOB_TILL_TIME
    current_time = datetime.now().time()
    must_be_scheduled = not is_time_between(from_time, till_time, current_time)
    
    if must_be_scheduled:
        #scheduler.enqueue_at(...)
        pass
    else:
        #scheduler.enqueue(...)
        pass