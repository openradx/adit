from typing import Any

from django.contrib.auth.models import Group
from django.template import Library

from adit_radis_shared.accounts.models import User

register = Library()


@register.simple_tag(takes_context=True)
def groups_of_user(context: dict[str, Any]):
    print("here")
    user: User = context["request"].user
    if user.is_staff:
        print("is staff", Group.objects.all())
        return Group.objects.all()
    else:
        return user.groups.all()
