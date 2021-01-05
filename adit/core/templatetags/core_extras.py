from datetime import datetime
from django.template import Library
from django.template.defaultfilters import join
from ..models import DicomJob, DicomTask

register = Library()


@register.filter
def person_name_from_dicom(value):
    """ See also :func:`adit.core.dicom_utils.person_name_to_dicom`"""
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


# TODO maybe we don't need this anymore as we convert all DICOM values
# with VM 1-n to lists even if there is only one item in it
# See :func:`adit.core.utils.dicom_connector._dictify_dataset`
@register.filter(is_safe=True, needs_autoescape=True)
def join_if_list(value, arg, autoescape=True):
    if isinstance(value, list):
        return join(value, arg, autoescape)

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
