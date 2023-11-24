from typing import Any, cast

from django.template import Library

from radis.accounts.models import User

from ..models import Report

register = Library()


@register.simple_tag(takes_context=True)
def collections_count(context: dict[str, Any], report: Report):
    user = cast(User, context["request"].user)
    return report.get_collections_count(user)
