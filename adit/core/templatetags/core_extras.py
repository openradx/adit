import logging
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
