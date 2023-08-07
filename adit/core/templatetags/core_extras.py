from datetime import datetime
from typing import Any, Literal

from django.conf import settings
from django.http import HttpRequest
from django.template import Library
from django.template.defaultfilters import join

from ..models import DicomJob, DicomTask
from ..utils.auth_utils import is_logged_in_user

register = Library()


@register.simple_tag(takes_context=True)
def theme(context: dict[str, Any]) -> Literal["light", "dark", "auto"]:
    request: HttpRequest = context["request"]

    theme = "auto"
    if is_logged_in_user(request.user):
        theme = request.user.preferences.get("theme", "auto")

    return theme


@register.simple_tag(takes_context=True)
def theme_color(
    context: dict[str, Any], theme: Literal["light", "dark", "auto"]
) -> Literal["light", "dark"]:
    # If the theme is auto we have to render something on the server, but the real theme
    # schema will be media queried on the client side.
    # TODO: Sec-CH-Prefers-Color-Scheme does not work yet,
    # see https://stackoverflow.com/q/76855062/166229
    request: HttpRequest = context["request"]
    color = request.headers.get("Sec-CH-Prefers-Color-Scheme", "light")
    if theme == "auto":
        return color  # type: ignore

    return theme


@register.filter
def access_item(dictionary, key):
    return dictionary[key]


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    dict_ = context["request"].GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.filter
def person_name_from_dicom(value):
    """See also :func:`adit.core.dicom_utils.person_name_to_dicom`"""
    if not value:
        return value

    return value.replace("^", ", ")


@register.simple_tag
def filter_modalities(modalities):
    exclude_modalities = settings.EXCLUDED_MODALITIES
    return [modality for modality in modalities if modality not in exclude_modalities]


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
