import logging
from datetime import date, datetime, time
from typing import Any

from django.conf import settings
from django.template import Library
from django.template.defaultfilters import join

from ..models import DicomJob, DicomTask

logger = logging.getLogger(__name__)

register = Library()


@register.inclusion_tag("core/_bootstrap_icon.html")
def bootstrap_icon(icon_name: str, size: int = 16):
    return {"icon_name": icon_name, "size": size}


@register.filter
def access_item(dictionary: dict[str, Any], key: str) -> Any:
    return dictionary[key]


@register.simple_tag(takes_context=True)
def url_replace(context: dict[str, Any], field: str, value: Any) -> str:
    dict_ = context["request"].GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.filter
def person_name_from_dicom(value: str) -> str:
    """See also :func:`adit.core.dicom_utils.person_name_to_dicom`"""
    if not value:
        return value

    return value.replace("^", ", ")


@register.simple_tag
def filter_modalities(modalities: list[str]) -> list[str]:
    exclude_modalities = settings.EXCLUDED_MODALITIES
    return [modality for modality in modalities if modality not in exclude_modalities]


# TODO maybe we don't need this anymore as we convert all DICOM values
# with VM 1-n to lists even if there is only one item in it
# See :func:`adit.core.utils.dicom_connector._dictify_dataset`
@register.filter(is_safe=True, needs_autoescape=True)
def join_if_list(value: Any, arg: str, autoescape=True) -> Any:
    if isinstance(value, list):
        return join(value, arg, autoescape)

    return value


@register.simple_tag
def combine_datetime(date: date, time: time) -> datetime:
    return datetime.combine(date, time)


@register.filter
def alert_class(tag: str) -> str:
    tag_map = {
        "info": "alert-info",
        "success": "alert-success",
        "warning": "alert-warning",
        "error": "alert-danger",
    }
    return tag_map.get(tag, "alert-secondary")


@register.filter
def message_symbol(tag: str) -> str:
    tag_map = {
        "info": "info",
        "success": "success",
        "warning": "warning",
        "error": "error",
    }
    return tag_map.get(tag, "bug")


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
