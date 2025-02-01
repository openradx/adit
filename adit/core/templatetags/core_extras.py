import logging

from django.template import Library

from ..models import DicomJob, DicomTask

logger = logging.getLogger(__name__)

register = Library()


@register.filter
def person_name_from_dicom(value: str) -> str:
    """See also :func:`adit.core.dicom_utils.person_name_to_dicom`"""
    if not value:
        return value

    return value.replace("^", ", ")


@register.filter
def dicom_job_status_css_class(status: DicomJob.Status) -> str:
    css_classes = {
        DicomJob.Status.UNVERIFIED: "text-info",
        DicomJob.Status.PENDING: "text-secondary",
        DicomJob.Status.IN_PROGRESS: "text-info",
        DicomJob.Status.CANCELING: "text-muted",
        DicomJob.Status.CANCELED: "text-muted",
        DicomJob.Status.SUCCESS: "text-success",
        DicomJob.Status.WARNING: "text-warning",
        DicomJob.Status.FAILURE: "text-danger",
    }
    return css_classes[status]


@register.filter
def dicom_task_status_css_class(status: DicomTask.Status) -> str:
    css_classes = {
        DicomTask.Status.PENDING: "text-secondary",
        DicomTask.Status.IN_PROGRESS: "text-info",
        DicomTask.Status.CANCELED: "text-muted",
        DicomTask.Status.SUCCESS: "text-success",
        DicomTask.Status.WARNING: "text-warning",
        DicomTask.Status.FAILURE: "text-danger",
    }
    return css_classes[status]
