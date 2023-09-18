import logging
import re
from datetime import date, datetime, time
from typing import Any

from django.conf import settings
from django.template import Library
from django.template.defaultfilters import join

logger = logging.getLogger(__name__)

register = Library()


@register.filter
def access_item(dictionary: dict[str, Any], key: str) -> Any:
    return dictionary[key]


@register.simple_tag(takes_context=True)
def url_replace(context: dict[str, Any], field: str, value: Any) -> str:
    dict_ = context["request"].GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.simple_tag
def filter_modalities(modalities: list[str]) -> list[str]:
    exclude_modalities = settings.EXCLUDED_MODALITIES
    return [modality for modality in modalities if modality not in exclude_modalities]


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


# TODO: Resolve reference names from another source in the context
# Context must be set in the view
@register.simple_tag(takes_context=True)
def url_abbreviation(context: dict, url: str):
    abbr = re.sub(r"^(https?://)?(www.)?", "", url)
    return abbr[:5]


@register.simple_tag
def calc_age(patient_birth_date: date, study_datetime: datetime):
    study_date = study_datetime.date()
    age = study_date.year - patient_birth_date.year
    if (study_date.month, study_date.day) < (patient_birth_date.month, patient_birth_date.day):
        age -= 1

    return age
