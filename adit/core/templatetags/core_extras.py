from datetime import datetime
from django.template import Library
from ..models import DicomJob, DicomTask

register = Library()


@register.filter
def person_name_from_dicom(value):
    if not value:
        return value

    return value.replace("^", ", ")


@register.simple_tag
def exclude_from_list(value, *args):
    if not value:
        return value

    if isinstance(value, list):
        return [item for item in value if item not in args]

    if value in args:
        return ""

    return value


@register.simple_tag
def combine_datetime(date, time):
    return datetime.combine(date, time)


@register.filter
def dicom_job_status_css_class(status):
    text_class = ""
    if status == DicomJob.Status.UNVERIFIED:
        text_class = "text-info"
    elif status == DicomJob.Status.PENDING:
        text_class = "text-secondary"
    elif status == DicomJob.Status.IN_PROGRESS:
        text_class = "text-info"
    elif status == DicomJob.Status.CANCELING:
        text_class = "text-muted"
    elif status == DicomJob.Status.CANCELED:
        text_class = "text-muted"
    elif status == DicomJob.Status.SUCCESS:
        text_class = "text-success"
    elif status == DicomJob.Status.WARNING:
        text_class = "text-warning"
    elif status == DicomJob.Status.FAILURE:
        text_class = "text-danger"
    return text_class


@register.filter
def dicom_task_status_css_class(status):
    text_class = ""
    if status == DicomTask.Status.PENDING:
        text_class = "text-secondary"
    elif status == DicomTask.Status.IN_PROGRESS:
        text_class = "text-info"
    elif status == DicomTask.Status.CANCELED:
        text_class = "text-muted"
    elif status == DicomTask.Status.SUCCESS:
        text_class = "text-success"
    elif status == DicomTask.Status.WARNING:
        text_class = "text-warning"
    elif status == DicomTask.Status.FAILURE:
        text_class = "text-danger"
    return text_class
